// Standalone exact-output check for the experimental final affine layer.
// Compile against either baseline or candidate using -I <checkout>/src.
#include "nnue/layers/affine_transform.h"

#include <array>
#include <cstdlib>
#include <iostream>
#include <random>
#include <sstream>
#include <string>

using namespace Stockfish;
using namespace Stockfish::Eval::NNUE;

template<unsigned Dimensions>
void check(std::mt19937& random) {
    using Layer = Layers::AffineTransform<Dimensions, 1>;
    Layer layer;
    alignas(64) std::array<u8, Layer::PaddedInputDimensions> input{};
    alignas(64) typename Layer::OutputBuffer output{};
    std::array<int, Dimensions> weights{};
    for (int trial = 0; trial < 10000; ++trial)
    {
        const int bias = int(random() % 2000001) - 1000000;
        std::string bytes;
        for (unsigned shift = 0; shift < 32; shift += 8)
            bytes.push_back(char(u32(bias) >> shift));
        for (unsigned i = 0; i < Layer::PaddedInputDimensions; ++i)
        {
            int weight = int(random() % 256) - 128;
            if (trial < 4)
                weight = trial & 1 ? 127 : -128;
            if (i < Dimensions)
                weights[i] = weight;
            bytes.push_back(char(weight));
        }
        std::istringstream stream(bytes, std::ios::binary);
        if (!layer.read_parameters(stream))
            std::abort();

        long long expected = bias;
        input.fill(0);
        for (unsigned i = 0; i < Dimensions; ++i)
        {
            const int activation = trial < 4 ? (trial & 2 ? 127 : 0) : random() % 128;
            input[Layer::get_weight_index(i)] = u8(activation);
            expected += activation * weights[i];
        }
        layer.propagate(input.data(), output);
        if (output[0] != expected)
        {
            std::cerr << "Mismatch: dimensions=" << Dimensions << " trial=" << trial
                      << " expected=" << expected << " actual=" << output[0] << '\n';
            std::exit(1);
        }
    }
    std::cout << Dimensions << " inputs: 10000 exact matches\n";
}

int main() {
    std::mt19937 random(20260918);
    check<16>(random);
    check<32>(random);
    check<64>(random);
    check<96>(random);
    check<128>(random);
    check<160>(random);
    check<192>(random);
    check<256>(random);
}
