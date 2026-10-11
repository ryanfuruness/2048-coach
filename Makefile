CXX ?= g++
NVCC ?= nvcc
CXXFLAGS ?= -O3 -march=native -std=c++17 -Wall -Wextra -Wno-unused-function -pthread
NVCCFLAGS ?= -O3 -arch=native -std=c++17 -Xcompiler "-O3 -march=native"
BUILD := build
HEADERS := $(wildcard src/*.h)

all: $(BUILD)/train $(BUILD)/play $(BUILD)/test_board $(BUILD)/endgame $(BUILD)/layered $(BUILD)/distill \
     $(BUILD)/analyze $(BUILD)/messy $(BUILD)/rollout $(BUILD)/coach
gpu: $(BUILD)/gpu_train

$(BUILD)/%.o: src/%.cpp $(HEADERS) | $(BUILD)
	$(CXX) $(CXXFLAGS) -c $< -o $@

# binaries are written under a temporary name and renamed, so rebuilding never
# disturbs a run that is using the old binary
$(BUILD)/train: $(BUILD)/train.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/play: $(BUILD)/play.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/endgame: $(BUILD)/endgame_tool.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/layered: $(BUILD)/layered_tool.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/distill: $(BUILD)/distill.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/analyze: $(BUILD)/analyze.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/rollout: $(BUILD)/rollout.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/messy: $(BUILD)/messy.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/coach: $(BUILD)/coach.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

# block formation detector and exact block tables (src/block.h; workstream pdf)
$(BUILD)/block_tool: $(BUILD)/block_tool.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/hm_tool: $(BUILD)/hm_tool.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/hm3_tool: $(BUILD)/hm3_tool.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

# your chance: the human player's own chances (workstream yc)
$(BUILD)/hv_tool: $(BUILD)/hv_tool.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

# counterfactual faithfulness of the analysis' reasons (workstream expl)
$(BUILD)/expl_tool: $(BUILD)/expl_tool.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

# packed networks for cheap serving (src/wpack.h; workstream serve)
$(BUILD)/wpack_tool: $(BUILD)/wpack_tool.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@.tmp && mv $@.tmp $@

$(BUILD)/test_board: $(BUILD)/test_board.o $(BUILD)/board.o
	$(CXX) $(CXXFLAGS) $^ -o $@

$(BUILD)/gpu_train: src/gpu_train.cu src/board.cpp $(HEADERS) | $(BUILD)
	$(NVCC) $(NVCCFLAGS) src/gpu_train.cu src/board.cpp -o $@.tmp && mv $@.tmp $@

$(BUILD):
	mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD)

.PHONY: all gpu clean
