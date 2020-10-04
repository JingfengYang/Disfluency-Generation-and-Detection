from table.modules.UtilClass import LayerNorm, Bottle, BottleLinear, \
    BottleLayerNorm, BottleSoftmax, Elementwise
#from table.modules.Gate import ContextGateFactory
from table.modules.GlobalAttention import GlobalAttention
#from table.modules.StackedRNN import StackedLSTM, StackedGRU
from table.modules.LockedDropout import LockedDropout
from table.modules.WeightDrop import WeightDrop
from table.modules.embed_regularize import embedded_dropout
from table.modules.position_ffn import PositionwiseFeedForward
from table.modules.multi_headed_attn import MultiHeadedAttention
#from table.modules.cross_entropy_smooth import CrossEntropyLossSmooth

# # For flake8 compatibility.
# __all__ = [GlobalAttention, ImageEncoder, CopyGenerator, MultiHeadedAttention,
#            LayerNorm, Bottle, BottleLinear, BottleLayerNorm, BottleSoftmax,
#            TransformerEncoder, TransformerDecoder, Elementwise,
#            MatrixTree, WeightNormConv2d, ConvMultiStepAttention,
#            CNNEncoder, CNNDecoder, StackedLSTM, StackedGRU, ContextGateFactory,
#            CopyGeneratorLossCompute, MultiHeadedAttention, PositionwiseFeedForward]
