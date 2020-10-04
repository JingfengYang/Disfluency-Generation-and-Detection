import torch
import torch.nn as nn

import table.IO
from table.modules.UtilClass import BottleLinear
from table.Utils import aeq
import torch.nn.functional as F


class GlobalAttention(nn.Module):
    """
    Luong Attention.

    Global attention takes a matrix and a query vector. It
    then computes a parameterized convex combination of the matrix
    based on the input query.


        H_1 H_2 H_3 ... H_n
          q   q   q       q
            |  |   |       |
              \ |   |      /
                      .....
                  \   |  /
                      a

    Constructs a unit mapping.
    $$(H_1 + H_n, q) => (a)$$
    Where H is of `batch x n x dim` and q is of `batch x dim`.

    Luong Attention (dot, general):
    The full function is
    $$\tanh(W_2 [(softmax((W_1 q + b_1) H) H), q] + b_2)$$.

    * dot: $$score(h_t,{\overline{h}}_s) = h_t^T{\overline{h}}_s$$
    * general: $$score(h_t,{\overline{h}}_s) = h_t^T W_a {\overline{h}}_s$$

    Bahdanau Attention (mlp):
    $$c = \sum_{j=1}^{SeqLength}\a_jh_j$$.
    The Alignment-function $$a$$ computes an alignment as:
    $$a_j = softmax(v_a^T \tanh(W_a q + U_a h_j) )$$.

    """

    def __init__(self, dim, is_transform_out, attn_type="dot", attn_hidden=0, context_size=None):
        super(GlobalAttention, self).__init__()

        self.dim = dim
        self.attn_type = attn_type
        self.attn_hidden = attn_hidden
        if context_size is None:
            self.context_size = dim
        else:
            self.context_size = context_size
        assert (self.attn_type in ["dot", "general", "mlp"]), (
            "Please select a valid attention type.")

        if attn_hidden > 0:
            self.transform_in = nn.Sequential(
                nn.Linear(dim, attn_hidden),
                nn.ELU(0.1))

        if self.attn_type == "general":
            d = attn_hidden if attn_hidden > 0 else dim
            self.linear_in = nn.Linear(d, d, bias=False)
            # initialization
            # self.linear_in.weight.data.add_(torch.eye(d))
        elif self.attn_type == "mlp":
            self.linear_context = BottleLinear(
                self.context_size, dim, bias=False)
            self.linear_query = nn.Linear(dim, dim, bias=True)
            self.v = BottleLinear(dim, 1, bias=False)
        # mlp wants it with bias
        out_bias = self.attn_type == "mlp"
        if is_transform_out:
            self.linear_out = nn.Linear(
                dim + self.context_size, dim, bias=out_bias)
        else:
            self.linear_out = None

        self.sm = nn.Softmax(dim=-1)
        self.tanh = nn.Tanh()
        self.mask = None
        self.ignore_small = 0

    def applyMask(self, mask):
        self.mask = mask

    def applyMaskBySeqBatch(self, q):
        self.applyMask(q.eq(table.IO.PAD).t().contiguous().unsqueeze(0))

    def score(self, h_t, h_s):
        """
        h_t (FloatTensor): batch x tgt_len x dim
        h_s (FloatTensor): batch x src_len x dim
        returns scores (FloatTensor): batch x tgt_len x src_len:
            raw attention scores for each src index
        """

        # Check input sizes
        src_batch, src_len, src_dim = h_s.size()
        tgt_batch, tgt_len, tgt_dim = h_t.size()
        aeq(src_batch, tgt_batch)
        # aeq(src_dim, tgt_dim)
        # aeq(self.dim, src_dim)

        if self.attn_type in ["general", "dot"]:
            if self.attn_hidden > 0:
                h_t = self.transform_in(h_t)
                h_s = self.transform_in(h_s)
            if self.attn_type == "general":
                h_t = self.linear_in(h_t)
            h_s_ = h_s.transpose(1, 2)
            # (batch, t_len, d) x (batch, d, s_len) --> (batch, t_len, s_len)
            return torch.bmm(h_t, h_s_)
        else:
            dim = self.dim
            wq = self.linear_query(h_t.view(-1, dim))
            wq = wq.view(tgt_batch, tgt_len, 1, dim)
            wq = wq.expand(tgt_batch, tgt_len, src_len, dim)

            uh = self.linear_context(
                h_s.contiguous().view(-1, self.context_size))
            uh = uh.view(src_batch, 1, src_len, dim)
            uh = uh.expand(src_batch, tgt_len, src_len, dim)

            # (batch, t_len, s_len, d)
            wquh = self.tanh(wq + uh)

            return self.v(wquh.view(-1, dim)).view(tgt_batch, tgt_len, src_len)

    def forward(self, input, context):
        """
        input (FloatTensor): batch x tgt_len x dim: decoder's rnn's output.
        context (FloatTensor): batch x src_len x dim: src hidden states

        Returns:
            (attn_h, align_vectors, concat_c)
            attn_h (FloatTensor): (tgt_len,batch,input_dim) linear and activte concat_c
            align_vectors (FloatTensor): (tgt_len,batch,src_len) probability
            concat_c (FloatTensor): (tgt_len,batch,src_dim+input_dim) Concat input and context vector
            or corresponding tgt_len=1 and squeeze

        """

        # one step input
        if input.dim() == 2:
            one_step = True
            input = input.unsqueeze(1)
        else:
            one_step = False

        batch, sourceL, dim = context.size()
        batch_, targetL, dim_ = input.size()
        aeq(batch, batch_)
        # aeq(dim, dim_)
        # aeq(self.dim, dim)

        if self.mask is not None:
            beam_, batch_, sourceL_ = self.mask.size()
            aeq(batch, batch_ * beam_)
            aeq(sourceL, sourceL_)

        # compute attention scores, as in Luong et al.
        align = self.score(input, context)

        if self.mask is not None:
            mask_ = self.mask.view(batch, 1, sourceL)  # make it broardcastable
            align.masked_fill_(mask_, -float('inf'))

        # Softmax to normalize attention weights
        align_vectors = self.sm(align.view(batch * targetL, sourceL))
        align_vectors = align_vectors.view(batch, targetL, sourceL)

        if self.ignore_small > 0:
            align_vectors = F.threshold(align_vectors, self.ignore_small, 0)

        # each context vector c_t is the weighted average
        # over all the source hidden states
        c = torch.bmm(align_vectors, context)

        # concatenate
        concat_c = torch.cat([c, input], 2)
        if self.linear_out is None:
            attn_h = concat_c
        else:
            attn_h = self.linear_out(concat_c)
            if self.attn_type in ["general", "dot"]:
                attn_h = self.tanh(attn_h)

        if one_step:
            attn_h = attn_h.squeeze(1)
            if self.linear_out is not None:
                concat_c = concat_c.squeeze(1)
            align_vectors = align_vectors.squeeze(1)
        else:
            attn_h = attn_h.transpose(0, 1).contiguous()
            if self.linear_out is not None:
                concat_c = concat_c.transpose(0, 1).contiguous()
            align_vectors = align_vectors.transpose(0, 1).contiguous()

        return attn_h, align_vectors, concat_c
