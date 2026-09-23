// Source-only diagnostic harness. Link against a selected Stockfish checkout's
// engine objects, omitting its main.o. No NNUE evaluation or game search is used.
// Optional arguments are text files containing one legal FEN per line.
#include "attacks.h"
#include "movegen.h"
#include "position.h"
#include "types.h"

#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using namespace Stockfish;

int main(int argc, char** argv) {
    Attacks::init();
    Position::init();
    std::vector<std::string> fens = {
      "4k3/4r3/8/2B5/8/8/8/4R1K1 w - - 0 1",  // Pinned black rook
      "4k3/3p4/8/8/6B1/8/8/6K1 w - - 0 1",   // King recapture available
      "4k3/3p4/8/8/6B1/8/8/3R2K1 w - - 0 1", // King recapture defended
      "4k3/P7/8/8/8/8/7p/4K3 w - - 0 1",     // Promotions
      "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",   // En passant
      "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", // Castling
    };
    for (int i = 1; i < argc; ++i) {
        std::ifstream input(argv[i]);
        if (!input) {
            std::cerr << "Cannot open " << argv[i] << '\n';
            return 1;
        }
        for (std::string fen; std::getline(input, fen);)
            if (!fen.empty())
                fens.push_back(fen);
    }

    std::uint64_t queries = 0, moves = 0, implicationCases = 0;
    std::array<std::uint64_t, 4> moveTypes{};
    for (const auto& fen : fens) {
        StateInfo state;
        Position position;
        if (position.set(fen, false, &state)) {
            std::cerr << "Invalid fixture FEN: " << fen << '\n';
            return 1;
        }
        for (Move move : MoveList<LEGAL>(position)) {
            ++moves;
            ++moveTypes[unsigned(move.type_of()) >> 14];
            const bool minus74 = position.see_ge(move, -74);
            bool observedFailure = false;
            for (int threshold = -4096; threshold <= 4096; ++threshold) {
                const bool result = position.see_ge(move, threshold);
                ++queries;
                if (result && observedFailure) {
                    std::cerr << "Nonmonotone SEE: " << fen << " move=" << move.raw()
                              << " threshold=" << threshold << '\n';
                    return 1;
                }
                observedFailure |= !result;
                if (threshold >= -74 && result) {
                    ++implicationCases;
                    if (!minus74) {
                        std::cerr << "Reuse implication failed: " << fen
                                  << " move=" << move.raw() << '\n';
                        return 1;
                    }
                }
            }
        }
    }
    for (unsigned type = 0; type < moveTypes.size(); ++type)
        if (!moveTypes[type]) {
            std::cerr << "Missing coverage for move type " << type << '\n';
            return 1;
        }
    std::cout << "positions=" << fens.size() << " legal_moves=" << moves
              << " threshold_queries=" << queries << " implications=" << implicationCases
              << " normal=" << moveTypes[0] << " promotion=" << moveTypes[1]
              << " en_passant=" << moveTypes[2] << " castling=" << moveTypes[3] << '\n';
}
