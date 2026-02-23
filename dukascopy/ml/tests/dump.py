import torch

# Load your specific model file
checkpoint = torch.load('checkpoints/model-best-gen94-f1-0.2105.pt', map_location='cpu')

# Extract the list
genes = checkpoint.get('feature_names', [])

# Print them with their index to find #10
for i, name in enumerate(genes):
    print(f"Index {i}: {name}")