// Compile with -S against each checkout to inspect the final layer's instructions.
#include "nnue/layers/affine_transform.h"
using Layer = Stockfish::Eval::NNUE::Layers::AffineTransform<128, 1>;
extern "C" __attribute__((noinline)) void final_affine(
  const Layer& layer, const Stockfish::u8* input, Stockfish::i32* output) {
    layer.propagate(input, output);
}
