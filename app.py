import json
import os
import random
import sqlite3
import time
from datetime import datetime
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_socketio import SocketIO, emit
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("VIGILANCE_DB", os.path.join(BASE, "vigilance.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vigilance_secret_key_123")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
patients_live = {}
socket_patient = {}
settings = {
    "movement": {"enabled": True, "rested": 0, "active": 5, "restless": 15, "unusualInactivity": 50, "bedUnoccupied": 12},
    "vitals": {"enabled": True, "spo2": {"threshold": 92, "belowThresholdMax": 100, "belowThresholdMin": 45, "aboveThresholdMax": 45, "aboveThresholdMin": 0}, "heartRate": {"lowerThreshold": 50, "upperThreshold": 100, "belowLowerMax": 40, "belowLowerMin": 0, "aboveUpperMin": 0, "aboveUpperMax": 30}, "temperature": {"lowerThreshold": 35, "upperThreshold": 37, "belowLowerMax": 15, "belowLowerMin": 0, "aboveUpperMin": 0, "aboveUpperMax": 35}},
    "fatigue": {"enabled": True, "eyeCloseThreshold": 0.07, "rules": [{"id": 1, "type": "eyes_open", "condition": ">", "seconds": 200, "points": 20}, {"id": 2, "type": "eyes_open", "condition": ">", "seconds": 100, "points": 10}]},
    "alerts": {"level1": {"enabled": True, "threshold": 20}, "level2": {"enabled": True, "threshold": 40}, "level3": {"enabled": True, "threshold": 60}},
}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS patients (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_name TEXT NOT NULL, age INTEGER NOT NULL, room_number TEXT NOT NULL, diagnosis TEXT DEFAULT 'General Observation', heart_rate REAL DEFAULT 75, spo2 REAL DEFAULT 98, temperature REAL DEFAULT 36.8, respiratory_rate REAL DEFAULT 16, blood_pressure TEXT DEFAULT '120/80', movement_state TEXT DEFAULT 'Resting', risk_score REAL DEFAULT 0, status TEXT DEFAULT 'Stable', user_id INTEGER, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER NOT NULL, patient_name TEXT NOT NULL, alert_type TEXT NOT NULL, severity TEXT NOT NULL, message TEXT NOT NULL, timestamp TEXT NOT NULL);
        """)


def patient_dict(row):
    if not row: return None
    p = dict(row)
    p["_id"] = str(p.pop("id"))
    p["updatedAt"] = p.pop("updated_at", None)
    return p


def user_payload(row):
    u = dict(row)
    u.pop("password", None)
    u["_id"] = str(u.pop("id"))
    if u["role"] == "patient":
        with db() as c: p = c.execute("SELECT * FROM patients WHERE user_id=?", (int(u["_id"]),)).fetchone()
        u["patientInfo"] = patient_dict(p)
    else: u["patientInfo"] = None
    u["token"] = str(u["_id"])
    return u


def current_user():
    uid = session.get("uid")
    if not uid: return None
    with db() as c: return c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def auth_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            u = current_user()
            if not u: return redirect(url_for("index"))
            if role and u["role"] != role: return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapped
    return deco


def score(data):
    movement = vital = posture = fatigue = 0
    pain = float(data.get("painScore") or 0)
    neuro = max(float(data.get("asymmetryScore") or 0), float(data.get("deliriumScore") or 0))
    mar = 20 if float(data.get("marScore") or 0) > .4 else 0
    m = settings["movement"]
    if m["enabled"]:
        state = data.get("movementState")
        movement = m["restless"] if state in ("High Restlessness", "Moderate Restlessness", "Restless") else m["unusualInactivity"] if state == "Unusual Inactivity" else m["active"] if state == "Active" else m["rested"]
        if data.get("bedOccupancy") is False: posture = m["bedUnoccupied"]
    elif data.get("bedOccupancy") is False: posture = 30
    posture = max(posture, 30 if data.get("headPosition") == "Collapsed" else 15 if data.get("headPosition") == "Abnormal Slump" else 0)
    v = settings["vitals"]
    if v["enabled"]:
        spo2 = data.get("spo2"); hr = data.get("heartRate"); temp = data.get("temperature")
        try:
            x=float(spo2); t=v["spo2"]; th=t["threshold"]
            vital += t["belowThresholdMin"] + max(0,(th-x)/th)*(t["belowThresholdMax"]-t["belowThresholdMin"]) if x<th else t["aboveThresholdMin"]+max(0,(100-x)/(100-th))*(t["aboveThresholdMax"]-t["aboveThresholdMin"])
        except (ValueError,TypeError,ZeroDivisionError): pass
        try:
            x=float(hr); t=v["heartRate"]
            if x<t["lowerThreshold"]: vital += t["belowLowerMin"]+max(0,(t["lowerThreshold"]-x)/t["lowerThreshold"])*(t["belowLowerMax"]-t["belowLowerMin"])
            elif x>t["upperThreshold"]: vital += t["aboveUpperMin"]+min(1,(x-t["upperThreshold"])/(220-t["upperThreshold"] if 220>t["upperThreshold"] else 1))*(t["aboveUpperMax"]-t["aboveUpperMin"])
        except (ValueError,TypeError,ZeroDivisionError): pass
        try:
            x=float(temp); t=v["temperature"]
            if x<t["lowerThreshold"]: vital += t["belowLowerMin"]+min(1,(t["lowerThreshold"]-x)/(t["lowerThreshold"]-30))*(t["belowLowerMax"]-t["belowLowerMin"])
            elif x>t["upperThreshold"]: vital += t["aboveUpperMin"]+min(1,(x-t["upperThreshold"])/(40-t["upperThreshold"]))*(t["aboveUpperMax"]-t["aboveUpperMin"])
        except (ValueError,TypeError,ZeroDivisionError): pass
    if settings["fatigue"]["enabled"]:
        matched = [r["points"] for r in settings["fatigue"]["rules"] if ((r["type"]=="eyes_closed" and data.get("eyesClosedSec",0)>r["seconds"]) or (r["type"]=="eyes_open" and data.get("eyesOpenSec",0)>r["seconds"]))]
        fatigue = max(matched) if matched else (20 if (data.get("eyesClosedSec") or 0)>5 else 10 if (data.get("eyesClosedSec") or 0)>3 else 0)
    total = min(100, int(movement+vital+posture+fatigue+pain+neuro+mar))
    a=settings["alerts"]
    status="Emergency" if a["level3"]["enabled"] and total>a["level3"]["threshold"] else "Nurse Alert" if a["level2"]["enabled"] and total>a["level2"]["threshold"] else "Observation Needed" if a["level1"]["enabled"] and total>a["level1"]["threshold"] else "Stable"
    return total,status


def broadcast_patients(): socketio.emit("update-patients", patients_live)


@app.route("/", methods=["GET"])
def index():
    u=current_user()
    if u: return redirect(url_for("portal"))
    return render_template("index.html")


@app.route("/portal")
@auth_required()
def portal(): return redirect(url_for("patient_page" if current_user()["role"]=="patient" else "caretaker_page"))


@app.route("/patient")
@auth_required("patient")
def patient_page(): return render_template("index.html", mode="patient", user=user_payload(current_user()))


@app.route("/caretaker")
@auth_required("caretaker")
def caretaker_page(): return render_template("index.html", mode="caretaker", user=user_payload(current_user()))


@app.post("/api/auth/register")
def register():
    d=request.get_json(silent=True) or request.form
    name,email,password,role=d.get("name"),d.get("email"),d.get("password"),d.get("role")
    role={"student":"patient","proctor":"caretaker"}.get(role,role)
    if not all((name,email,password)) or role not in ("patient","caretaker"): return jsonify(message="Name, email, password and a valid role are required"),400
    try:
        with db() as c:
            cur=c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",(name,email,generate_password_hash(password),role)); uid=cur.lastrowid
            if role=="patient": c.execute("INSERT INTO patients(patient_name,age,room_number,diagnosis,user_id,updated_at) VALUES(?,?,?,?,?,?)",(name,int(d.get("age") or random.randint(30,79)),d.get("room_number") or f"ICU-{random.randint(101,110)}",d.get("diagnosis") or "Post-operative Recovery",uid,datetime.now().isoformat()))
    except sqlite3.IntegrityError: return jsonify(message="Account already exists"),400
    with db() as c: u=c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
    return jsonify(user_payload(u)),201


@app.post("/api/auth/login")
def login():
    d=request.get_json(silent=True) or request.form
    with db() as c: u=c.execute("SELECT * FROM users WHERE email=?",(d.get("email"),)).fetchone()
    if not u or not check_password_hash(u["password"],d.get("password") or ""): return jsonify(message="Invalid email or password"),401
    session["uid"]=u["id"]
    return jsonify(user_payload(u))


@app.post("/api/auth/logout")
def logout(): session.clear(); return jsonify(message="Logged out")


@app.route("/api/patient",methods=["GET","POST"])
def patient_collection():
    if request.method=="GET":
        with db() as c: rows=c.execute("SELECT * FROM patients").fetchall()
        return jsonify([patient_dict(x) for x in rows])
    d=request.get_json() or {}
    with db() as c:
        cur=c.execute("INSERT INTO patients(patient_name,age,room_number,diagnosis,updated_at) VALUES(?,?,?,?,?)",(d.get("patient_name"),d.get("age"),d.get("room_number"),d.get("diagnosis","General Observation"),datetime.now().isoformat())); row=c.execute("SELECT * FROM patients WHERE id=?",(cur.lastrowid,)).fetchone()
    return jsonify(patient_dict(row)),201


@app.route("/api/patient/<pid>",methods=["GET","PUT"])
def patient_item(pid):
    with db() as c: row=c.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone()
    if not row: return jsonify(message="Patient not found"),404
    if request.method=="GET": return jsonify(patient_dict(row))
    d=request.get_json() or {}; allowed={"heart_rate":"heart_rate","spo2":"spo2","temperature":"temperature","respiratory_rate":"respiratory_rate","blood_pressure":"blood_pressure","movement_state":"movement_state","risk_score":"risk_score","status":"status"}
    sets=[f"{k}=?" for k in allowed if k in d]; vals=[d[k] for k in allowed if k in d]
    if sets:
        with db() as c: c.execute(f"UPDATE patients SET {','.join(sets)},updated_at=? WHERE id=?",(*vals,datetime.now().isoformat(),pid)); row=c.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone()
    return jsonify(patient_dict(row))


@app.route("/api/alerts",methods=["GET","POST"])
def alert_collection():
    if request.method=="GET":
        with db() as c: rows=c.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 100").fetchall()
        return jsonify([dict(x, _id=str(x["id"])) for x in rows])
    d=request.get_json() or {}; now=datetime.now().isoformat()
    try:
        with db() as c:
            cur=c.execute("INSERT INTO alerts(patient_id,patient_name,alert_type,severity,message,timestamp) VALUES(?,?,?,?,?,?)",(d["patient_id"],d["patient_name"],d["alert_type"],d.get("severity","Observation Needed"),d["message"],now)); row=c.execute("SELECT * FROM alerts WHERE id=?",(cur.lastrowid,)).fetchone()
        return jsonify(dict(row,_id=str(row["id"])),201)
    except (KeyError,sqlite3.Error) as e: return jsonify(message=str(e)),400


@app.get("/api/alerts/patient/<pid>")
def patient_alerts(pid):
    with db() as c: rows=c.execute("SELECT * FROM alerts WHERE patient_id=? ORDER BY timestamp DESC",(pid,)).fetchall()
    return jsonify([dict(x,_id=str(x["id"])) for x in rows])


@app.get("/api/caretaker")
def caretakers():
    with db() as c: rows=c.execute("SELECT id,name,email,role FROM users WHERE role='caretaker'").fetchall()
    return jsonify([dict(x,_id=str(x["id"])) for x in rows])


@app.get("/api/icu-monitor/<room>")
def icu_monitor(room):
    with db() as c: n=c.execute("SELECT COUNT(*) n FROM patients WHERE room_number=?",(room,)).fetchone()["n"]
    return jsonify(room=room,monitoringActive=n>0,patientCount=n,systemHealth="Optimal",videoFeedStatus="Connected",vitalsTelemetry="Active")


@app.post("/simulate")
def simulate():
    d=request.get_json(silent=True) or {}; room,mode=d.get("room"),d.get("mode")
    if not room or not mode: return jsonify(error="Room and mode are required"),400
    socketio.emit("set-simulation-mode",{"room":room,"mode":mode})
    return jsonify(message=f"Simulation mode {mode} sent to room {room}")


@app.post("/sensor")
def sensor():
    room=request.args.get("room")
    if not room: return jsonify(error="Room is required"),400
    d=request.get_json(silent=True) or {}; packet={"room":room,"heart_rate":d.get("heart_rate"),"spO2":d.get("spO2"),"temp":d.get("temp"),"resp_rate":d.get("resp_rate"),"ABP":d.get("ABP")}
    socketio.emit("sensor-data",packet)
    return jsonify(room=room,sys_time=int(time.time()))


@socketio.on("connect")
def on_connect(): emit("update-patients",patients_live)


@socketio.on("patient-join")
def patient_join(data):
    name=data.get("name") or "Unknown Patient"; pid=data.get("patientId")
    with db() as c:
        row=c.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone() if pid and str(pid).isdigit() else c.execute("SELECT * FROM patients WHERE patient_name=? ORDER BY updated_at DESC LIMIT 1",(name,)).fetchone()
    p=patient_dict(row) if row else {"_id":pid or f"mock_pat_{request.sid}","patient_name":name,"age":data.get("age",65),"room_number":data.get("roomNumber","ICU-102"),"diagnosis":data.get("diagnosis","Post-operative Observation"),"heart_rate":"-","spo2":"-","temperature":"-","respiratory_rate":"-","blood_pressure":"-","movement_state":"Resting","risk_score":0,"status":"Stable"}
    sid=request.sid; socket_patient[sid]=p["_id"]
    patients_live[sid]={"patientId":p["_id"],"name":p["patient_name"],"age":p["age"],"roomNumber":p["room_number"],"diagnosis":p["diagnosis"],"heartRate":p["heart_rate"],"spo2":p["spo2"],"temperature":p["temperature"],"respiratoryRate":p["respiratory_rate"],"bloodPressure":p["blood_pressure"],"movementState":p["movement_state"],"riskScore":p["risk_score"],"status":p["status"],"bedOccupancy":True,"headPosition":"Normal","eyesClosedSec":0,"painScore":0,"asymmetryScore":0,"marScore":0,"deliriumScore":0,"lastAlertTime":{},"videoFrame":None,"timeline":[{"time":datetime.now().strftime("%H:%M:%S"),"event":"ICU Monitoring Session Initiated","severity":"Stable"}]}
    broadcast_patients()


@socketio.on("get-risk-settings")
def get_settings(): emit("risk-settings-updated",settings)


@socketio.on("update-risk-settings")
def update_settings(data):
    global settings
    settings=data
    for p in patients_live.values(): p["riskScore"],p["status"]=score(p)
    broadcast_patients(); socketio.emit("risk-settings-updated",settings)


@socketio.on("update-patient-state")
def update_patient(data):
    p=patients_live.get(request.sid)
    if not p: return
    keys={"heartRate":"heartRate","spo2":"spo2","temperature":"temperature","respiratoryRate":"respiratoryRate","bloodPressure":"bloodPressure","movementState":"movementState","bedOccupancy":"bedOccupancy","headPosition":"headPosition","eyesClosedSec":"eyesClosedSec","eyesOpenSec":"eyesOpenSec","painScore":"painScore","asymmetryScore":"asymmetryScore","marScore":"marScore","deliriumScore":"deliriumScore","videoFrame":"videoFrame"}
    for key in keys:
        if key in data: p[key]=data[key]
    p["riskScore"],p["status"]=score(p); now=time.time(); level=3 if p["status"]=="Emergency" else 2 if p["status"]=="Nurse Alert" else 1 if p["status"]=="Observation Needed" else 0
    if level:
        typ=f"Level-{level} {'Emergency' if level==3 else 'Warning' if level==2 else 'Notice'}"
        if now-p["lastAlertTime"].get(typ,0)>=10:
            p["lastAlertTime"][typ]=now; severity=p["status"]; msg=f"Risk score ({p['riskScore']}) exceeded Level-{level} threshold."; stamp=datetime.now().strftime("%H:%M:%S")
            p["timeline"].insert(0,{"time":stamp,"event":f"{typ}: {msg}","severity":severity}); p["timeline"]=p["timeline"][:20]
            pid=p["patientId"]
            if str(pid).isdigit():
                with db() as c: c.execute("INSERT INTO alerts(patient_id,patient_name,alert_type,severity,message,timestamp) VALUES(?,?,?,?,?,?)",(int(pid),p["name"],typ,severity,msg,datetime.now().isoformat()))
            socketio.emit("emergency-notification",{"patientId":pid,"patientName":p["name"],"roomNumber":p["roomNumber"],"alertType":typ,"severity":severity,"message":msg,"timestamp":stamp})
    pid=p["patientId"]
    if str(pid).isdigit():
        with db() as c: c.execute("UPDATE patients SET heart_rate=?,spo2=?,temperature=?,respiratory_rate=?,blood_pressure=?,movement_state=?,risk_score=?,status=?,updated_at=? WHERE id=?",(p["heartRate"],p["spo2"],p["temperature"],p["respiratoryRate"],p["bloodPressure"],p["movementState"],p["riskScore"],p["status"],datetime.now().isoformat(),int(pid)))
    broadcast_patients()


@socketio.on("sensor-data")
def sensor_to_patient(data):
    for sid,p in patients_live.items():
        if p.get("roomNumber")==data.get("room"):
            packet={"heartRate":data.get("heart_rate"),"spo2":data.get("spO2"),"temperature":data.get("temp"),"respiratoryRate":data.get("resp_rate"),"bloodPressure":data.get("ABP")}
            socketio.emit("sensor-data",packet,to=sid)


@socketio.on("request-video")
def request_video(d): socketio.emit("viewer-join",{"viewerId":request.sid},to=d.get("targetId"))

for event in ("webrtc-offer","webrtc-answer","webrtc-ice-candidate"):
    def relay(data, ev=event): socketio.emit(ev,{**data,"senderId":request.sid},to=data.get("targetId"))
    socketio.on(event,relay)


@socketio.on("disconnect")
def disconnect():
    patients_live.pop(request.sid,None); socket_patient.pop(request.sid,None); broadcast_patients()


init_db()
if __name__ == "__main__": socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=True)
