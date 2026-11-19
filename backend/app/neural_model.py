"""Small experimental transformer encoder for supervised category experiments.

This is not a general-purpose language model. It requires curated, labelled
examples and is intentionally separate from retrieval-grounded production chat.
"""
import torch
from torch import nn

class InsuranceTextClassifier(nn.Module):
    def __init__(self,vocab_size:int,num_labels:int,dim:int=128,heads:int=4,layers:int=2,max_length:int=256):
        super().__init__()
        self.token_embedding=nn.Embedding(vocab_size,dim,padding_idx=0)
        self.position_embedding=nn.Embedding(max_length,dim)
        block=nn.TransformerEncoderLayer(d_model=dim,nhead=heads,dim_feedforward=dim*4,batch_first=True,norm_first=True)
        self.encoder=nn.TransformerEncoder(block,num_layers=layers)
        self.norm=nn.LayerNorm(dim)
        self.classifier=nn.Linear(dim,num_labels)
        self.max_length=max_length
    def forward(self,input_ids,attention_mask=None):
        ids=input_ids[:,:self.max_length]
        positions=torch.arange(ids.size(1),device=ids.device).unsqueeze(0)
        x=self.token_embedding(ids)+self.position_embedding(positions)
        padding_mask=(attention_mask[:,:ids.size(1)]==0) if attention_mask is not None else None
        x=self.encoder(x,src_key_padding_mask=padding_mask)
        if padding_mask is None: pooled=x.mean(dim=1)
        else:
            keep=(~padding_mask).unsqueeze(-1)
            pooled=(x*keep).sum(dim=1)/keep.sum(dim=1).clamp(min=1)
        return self.classifier(self.norm(pooled))
