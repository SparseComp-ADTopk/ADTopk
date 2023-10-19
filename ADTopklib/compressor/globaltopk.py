import torch

from ADTopklib import Compressor
import random
import horovod.torch as hvd
import numpy as np


class GlobalTopkCompressor(Compressor):

    def __init__(self, compress_ratio, rank):
        super().__init__()

        self.compress_ratio = compress_ratio
        self.rank = rank
        self.epoch=0
        self.iteration=0
        self.index=0
        self.layernumels={}
        self.thres_mean_arr=[]

        self.tensor_flatten_np_arr=[]
        self.values_flatten_global_np_arr=[]
        self.values_flatten_channel_np_arr=[]


    # tensor稀疏化得到top-k的稀疏值
    def sparsify(self, tensor, compress_ratio,epoch, name):
        
        # compress_ratio=0.001
        compress_ratio=0.1
        # compress_ratio=0.05
        
        numel = tensor.numel()
        shape =tensor.shape
        
        if True:

            # Global Top-k
            tensor_flatten=tensor.flatten().cuda()
            k= max(1, int(numel * compress_ratio))
            _, indices_flatten_global = torch.topk(tensor_flatten.abs(), k, sorted=False,)
            values_flatten_global = torch.gather(tensor_flatten, 0, indices_flatten_global)
            return values_flatten_global, indices_flatten_global


    # tensor反稀疏化
    def desparsify(self, tensors, numel, shape):
        values, indices = tensors
        # if True:
        if values.numel()==numel:
            return values
        else:
            # All-Channel Top-k
            # tensor_decompressed = torch.zeros(
            #     shape, dtype=values.dtype, layout=values.layout, device=values.device).cuda()
            # if shape[0]>shape[1]:
            #     tensor_decompressed.scatter_(0, indices, values)
            # else:
            #     tensor_decompressed.scatter_(1, indices, values)
            
            # Global Top-k
            tensor_decompressed = torch.zeros(
                numel, dtype=values.dtype, layout=values.layout, device=values.device).cuda()
            tensor_decompressed.scatter_(0, indices, values)

            return tensor_decompressed
    

    # 抽象方法重载compress
    def compress(self, tensor, name):

        tensors = self.sparsify(tensor, self.compress_ratio,self.epoch, name)
        ctx = tensor.numel(), tensor.size()
        return tensors, ctx

    def show_sparsify(self, tensor):
        # if self.rank==0:
        print('----------'+str(self.rank)+'----------')
        print(tensor.shape)
        tensor = tensor.flatten()
        print(tensor)

    def decompress(self, tensors, ctx,name):
        """Decompress by filling empty slots with zeros and reshape back using the original shape"""
        
        
        if ctx==None:
            tensor, = tensors
            return tensor
        numel, shape = ctx
        
        tensor_decompressed =self.desparsify(tensors, numel,shape) 

        return tensor_decompressed.view(shape)
    
    def decompress_add(self, tensors, ctx, name):
        numel, shape = ctx
        if ctx==None:
            tensor, = tensors
            return tensor
        
        values, indices = tensors
        if values.numel()==numel:
            return values
        # 返回一个形状为为size,类型为torch.dtype,里面的每一个值都是0的tensor
        tensor_decompressed = torch.zeros(
            numel, dtype=values.dtype, layout=values.layout, device=values.device).cuda()
        tensor_decompressed = tensor_decompressed.scatter_add(0, indices, values)
        return tensor_decompressed.view(shape)