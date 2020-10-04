import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

def _is_long(x):
    if hasattr(x, 'data'):
        x = x.data
    return isinstance(x, torch.LongTensor) or isinstance(x, torch.cuda.LongTensor)


def cross_entropy(logits, target, weight=None, size_average=True,
                  ignore_index=None, smooth_eps=None, smooth_dist=None):
    """cross entropy loss, with support for target distributions and label smoothing https://arxiv.org/abs/1512.00567"""
    if smooth_eps is not None and smooth_eps > 0:
        num_classes = logits.size(-1)
        mask_idx = None
        if _is_long(target):
            if ignore_index:
                mask_idx = target.eq(ignore_index)
            target = onehot(target, num_classes).type_as(logits)
        if smooth_dist is None:
            target = (1 - smooth_eps) * target + \
                smooth_eps / num_classes
        else:
            target = torch.lerp(
                target, smooth_dist.unsqueeze(0), smooth_eps)
        if mask_idx is not None:
            target.masked_fill_(mask_idx.unsqueeze(1), 0)
    if weight is not None:
        target = target * weight.unsqueeze(0)
    ce = -(logits * target).sum(1)
    if size_average:
        ce = ce.mean()
    else:
        ce = ce.sum()
    return ce


class CrossEntropyLossSmooth(nn.CrossEntropyLoss):
    """CrossEntropyLossSmooth - with ability to recieve distrbution as targets, and optional label smoothing"""

    def __init__(self, weight=None, size_average=True, ignore_index=-100, reduce=True,
                 smooth_eps=None, smooth_dist=None):
        super(CrossEntropyLossSmooth, self).__init__(
            weight, size_average=size_average, ignore_index=ignore_index)
        self.smooth_eps = smooth_eps
        self.smooth_dist = smooth_dist

    def forward(self, input, target):
        return cross_entropy(input, target, self.weight, self.size_average,
                             self.ignore_index, self.smooth_eps, self.smooth_dist)
