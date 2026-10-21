import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# 1. Load files
ground_truth_file = 'breath_data_pramod.csv'
predictions_file = 'totest_result.csv'

df_truth = pd.read_csv(ground_truth_file)
df_pred = pd.read_csv(predictions_file)

y_true = df_truth['Breath_Active']
y_pred = df_pred['Breath_Active']

# 2. Compute Accuracy Metrics
total_samples = len(y_true)
correct = np.sum(y_true == y_pred)
accuracy = accuracy_score(y_true, y_pred)
cm = confusion_matrix(y_true, y_pred)

print(f"=== Comparison Summary ===")
print(f"Total Samples Tested: {total_samples}")
print(f"Correct Predictions : {correct} / {total_samples}")
print(f"Accuracy Score      : {accuracy * 100:.2f}%\n")
print("Detailed Classification Report:")
print(classification_report(y_true, y_pred, target_names=['Inactive', 'Active']))

# 3. Plot Confusion Matrix & Class Distribution Charts
fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))

# Plot 1: Confusion Matrix
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax[0],
            xticklabels=['Inactive', 'Active'], yticklabels=['Inactive', 'Active'])
ax[0].set_title(f'Confusion Matrix (Accuracy: {accuracy*100:.1f}%)')
ax[0].set_xlabel('Predicted (totest_result.csv)')
ax[0].set_ylabel('Actual Ground Truth (breath_data_pramod.csv)')

# Plot 2: Class Distribution Comparison
counts = pd.DataFrame({
    'Ground Truth': y_true.value_counts(),
    'Predicted': y_pred.value_counts()
}).rename(index={0: 'Inactive (0)', 1: 'Active (1)'})

counts.plot(kind='bar', ax=ax[1], color=['#2b5c8f', '#e07a5f'])
ax[1].set_title('Actual vs Predicted Distribution')
ax[1].set_ylabel('Count')
ax[1].set_xticklabels(ax[1].get_xticklabels(), rotation=0)

# Add counts on top of bars
for p in ax[1].patches:
    ax[1].annotate(str(int(p.get_height())), 
                (p.get_x() + p.get_width() / 2., p.get_height() / 2),
                ha='center', va='center', color='white', fontweight='bold')

plt.tight_layout()
chart_path = 'comparison_result.png'
plt.savefig(chart_path)
print(f"Chart saved as '{chart_path}'")