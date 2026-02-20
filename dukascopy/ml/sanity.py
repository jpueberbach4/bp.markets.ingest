import torch
from collections import OrderedDict

# Verify the Atomic Snapshot
# Updated for PyTorch 2.4+ security standards
ckpt = torch.load('checkpoints/best_model_gen_30.pt', map_location='cpu', weights_only=True)

print(f"✅ Checkpoint Gen: {ckpt['gen']}") # Should be 30 
print(f"✅ Genes Found: {len(ckpt['genes'])}") # Should be 24 

# Validate weight shapes match your Factory Specs 
for key, tensor in ckpt['state_dict'].items():
    print(f"Layer {key}: {tensor.shape}")