import joblib
import matplotlib.pyplot as plt
from sklearn.tree import plot_tree
import numpy as np

# pip3 install matplotlib
# Load the model
model = joblib.load('GBP-USD-engine.pkl')

# Feature names from your training script
features = ['Trend Deviation', 'RSI Normalized', 'Volatility Ratio', 'Body Strength']
importances = model.feature_importances_
indices = np.argsort(importances)

# Plot
plt.figure(figsize=(10, 6))
plt.title('AI Logic: What weights more in a GBP-USD Bottom?')
plt.barh(range(len(indices)), importances[indices], color='#FF6D00', align='center')
plt.yticks(range(len(indices)), [features[i] for i in indices])
plt.xlabel('Relative Importance')
plt.savefig('feature_importance.png')

# Pick one of the 200 trees (e.g., the first one)
plt.figure(figsize=(20, 10))
plot_tree(model.estimators_[0], 
          feature_names=features, 
          max_depth=2, # Limiting depth for readability
          filled=True, 
          rounded=True, 
          class_names=['No Trade', 'Bottom'])
plt.savefig('decision_tree_logic.png')