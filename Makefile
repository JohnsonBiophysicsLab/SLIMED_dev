#  Update 2025-08-12:
#  o Add flags for codecov
#                                                            Moon yying7@jh.edu
#
#  Update 2020-01-29: 
#  o Uses required argument of serial, omp, or mpi. 
#  o Use VPATH for finding cpp file in different directories -- this simplifies rules
#  o Abort if gsl-config isn't available
#  o Fixed (INTEL) compiler search 0=found | 1=notfound ; make conditional simple (ifeq 0|1)
#  o Also use conditional for GCC
#  o For objects, use basename to get base file name
#  o Clean up directory prefix (shorten variable names and group)
#  o Simplified obj and bin rule logic and readability.
#  o put rules in canonical order
#  o Now has PROF for profiling. (This is by default overrided with empty PROF.)
#  o Now uses INCS. CXXFLAGS is used for C++ specific options.
#  o Make executables with suffixes ( continuum_membrane_serial | continuum_membrane_mpi | continuum_membrane_omp).
#  --  a bit cleaner                                            Kent milfeld@tacc.utexas.edu
#
# TODO: use function to create VPATH
# TODO: Make rules for *.hpp's
#
# Set terminal width to 220 to avoid viewing wrapped lines in output. A width of 200 avoids most wrapping.


# LDFLAGS = -larmadillo
#  -- armadillo is not a dependency any more. (changed 2022)

VPATH = \
	src/ \
	src/io \
	src/math \
	src/parser \
	src/energy_force \
	src/cuda \
	src/mesh \
	src/parameters \
	src/diffusion \
	src/vector_math \
	src/dynamics \
	src/gsl_matrix_methods \
	src/linear_algebra \
	src/model

BDIR   = bin
EDIR   = EXEs
ODIR   = obj
SDIR   = src
EPDIR  = EXE_PAR
ECDIR = EXE_CLUSTER

# Keep the standalone Step-1 diagnostics independent of the simulation's GSL
# dependency. Ordinary/default and mixed simulation builds retain the existing
# GSL requirement.
CUDA_BACKEND_DIAGNOSTIC_GOALS := cuda_backend_report cuda_backend_stub_report \
	cuda_mesh_state_report cuda_mesh_state_stub_report
CUDA_BACKEND_ONLY := $(if $(MAKECMDGOALS),$(if $(filter-out $(CUDA_BACKEND_DIAGNOSTIC_GOALS),$(MAKECMDGOALS)),,1),)

# Detect Operating System
UNAME_S := $(shell uname -s)

# Default OpenMP settings (Ubuntu/Linux)
OMP_INC   = 
OMP_LIB   = 
OMP_FLAGS = -fopenmp

# MacOS compatibility
ifeq ($(UNAME_S), Darwin)
    # Use Homebrew GCC for OpenMP builds, but use the platform C++ ABI for
    # tests so Homebrew's GoogleTest libraries link correctly.
    ifeq (test,$(MAKECMDGOALS))
        CC      = clang++
    else
        CC      = g++-15
    endif
    CXX     = $(CC)
    OMP_FLAGS = -fopenmp

    # Standard OMP paths
    # Remove -Xclang or explicit Homebrew libomp paths for this setup
    OMP_INC   = 
    OMP_LIB   = 
    
    # 2. Force the compiler to use the correct C++ standard library and architecture
    # This usually fixes the "Undefined symbols" for std::string/ostream
    #CXXFLAGS += -stdlib=libc++ -arch arm64
    
endif


# Add test to path if enabled
ifeq (test,$(MAKECMDGOALS))
	ODIR = obj/test
	VPATH += tests
	SDIR += tests
endif

# Set minimum version to C++17. GoogleTest 1.17+ requires C++17, so all
# build and test targets use the same standard.
CXX_STD ?= c++17
CXXFLAGS = -std=$(CXX_STD)

# Enable coverage for "coverage" and "test" targets
# --- Coverage toggle (OFF by default)
COVERAGE ?= 0

# GCC/g++ coverage (works on Linux easily)
ifeq ($(COVERAGE),1)
  CFLAGS   += -O0 -g --coverage
  CXXFLAGS += -O0 -g --coverage
  LDFLAGS  += --coverage
  # Optional: ensure gcov is linked explicitly
  # LIBS += -lgcov
endif

# (Optional) If you use Clang/LLVM for coverage instead of GCC,
# use COVERAGE=llvm and uncomment this block:
ifeq ($(COVERAGE),llvm)
  CFLAGS   += -O0 -g -fprofile-instr-generate -fcoverage-mapping
  CXXFLAGS += -O0 -g -fprofile-instr-generate -fcoverage-mapping
  LDFLAGS  += -fprofile-instr-generate
endif


PROF   = 

.PHONY: any

#               REQUIREMENTS: gls and directories

ifeq ($(CUDA_BACKEND_ONLY),1)
$(shell mkdir -p bin)
$(shell mkdir -p $(ODIR))
else
hasGSL = $(shell type gsl-config >/dev/null 2>&1; echo $$?)
ifeq ($(hasGSL),1)
$(error " GSL must be installed, and gsl-config must be in path.")
else
$(shell mkdir -p bin)
$(shell mkdir -p $(ODIR))
endif
endif

#               EXECUTABLE SETUP for serial, MPI, OpenMP (omp), cluster
#
ifeq ($(CUDA_BACKEND_ONLY),1)
INCS = -Iinclude -Iinclude/*
LIBS =
else
INCS = $(shell gsl-config --cflags) -Iinclude -Iinclude/*
LIBS = $(shell gsl-config --libs)
endif

USE_OPENSUBDIV_REGULAR ?= 0
ifeq ($(USE_OPENSUBDIV_REGULAR),1)
	ifeq ($(OPENSUBDIV_ROOT),)
		$(error "USE_OPENSUBDIV_REGULAR=1 requires OPENSUBDIV_ROOT=/path/to/opensubdiv")
	endif
	DEFS += -DUSE_OPENSUBDIV_REGULAR
	INCS += -I$(OPENSUBDIV_ROOT)/include
	LIBS += -L$(OPENSUBDIV_ROOT)/lib -L$(OPENSUBDIV_ROOT)/lib64 -Wl,-rpath,$(OPENSUBDIV_ROOT)/lib -Wl,-rpath,$(OPENSUBDIV_ROOT)/lib64 -losdCPU
endif

USE_OPENSUBDIV_VALENCE5 ?= 0
ifeq ($(USE_OPENSUBDIV_VALENCE5),1)
	ifeq ($(OPENSUBDIV_ROOT),)
		$(error "USE_OPENSUBDIV_VALENCE5=1 requires OPENSUBDIV_ROOT=/path/to/opensubdiv")
	endif
	DEFS += -DUSE_OPENSUBDIV_VALENCE5
	INCS += -I$(OPENSUBDIV_ROOT)/include
	LIBS += -L$(OPENSUBDIV_ROOT)/lib -L$(OPENSUBDIV_ROOT)/lib64 -Wl,-rpath,$(OPENSUBDIV_ROOT)/lib -Wl,-rpath,$(OPENSUBDIV_ROOT)/lib64 -losdCPU
endif

# Optional GoogleTest prefix. This lets `make test` find Homebrew's keg on
# macOS while preserving the default system paths used by Linux packages.
GTEST_PREFIX ?= $(shell command -v brew >/dev/null 2>&1 && brew --prefix googletest 2>/dev/null)
ifneq ($(GTEST_PREFIX),)
	GTEST_INCS = -I$(GTEST_PREFIX)/include
	GTEST_LIBS = -L$(GTEST_PREFIX)/lib
endif

LIBOMP_PREFIX ?= $(shell command -v brew >/dev/null 2>&1 && brew --prefix libomp 2>/dev/null)
ifneq ($(LIBOMP_PREFIX),)
	LIBOMP_INCS = -I$(LIBOMP_PREFIX)/include
endif

ifeq (serial,$(MAKECMDGOALS))
	_EXEC = continuum_membrane
endif

ifeq (dyna,$(MAKECMDGOALS))
	_EXEC = membrane_dynamics
endif

ifeq (mpi,$(MAKECMDGOALS))
	_EXEC = continuum_membrane
         DEFS += -DMPI
endif

ifeq (omp,$(MAKECMDGOALS))
    _EXEC  = continuum_membrane
    DEFS   += -DOMP
    PLANG  = $(OMP_FLAGS)
    INCS  += $(OMP_INC)
    LIBS  += $(OMP_LIB)
endif

ifeq (multi,$(MAKECMDGOALS))
	_EXEC = continuum_membrane_multithreading
endif

ifeq (dyna_omp,$(MAKECMDGOALS))
    _EXEC = membrane_dynamics
    DEFS  += -DOMP
    PLANG = $(OMP_FLAGS)
    INCS += $(OMP_INC)
    LIBS += $(OMP_LIB)
endif

ifeq (dyna_multi,$(MAKECMDGOALS))
	_EXEC = membrane_dynamics_multithreading
endif

ifeq (test,$(MAKECMDGOALS))
	_EXEC = test_main
endif

ifeq (clean,$(MAKECMDGOALS))
	MAKECMDGOALS = dummy
endif

EXEC  = $(patsubst %,$(BDIR)/%,$(_EXEC))


OS    := $(shell uname)
INTEL  = $(shell type icpc  >/dev/null 2>&1; echo $$?)
GCC    = $(shell type g++   >/dev/null 2>&1; echo $$?)



# Add pthread to library if multithreading (embarrassingly parallel) is needed
ifeq (multi,$(MAKECMDGOALS))
	LIBS += -pthread
endif

ifeq (dyna_multi,$(MAKECMDGOALS))
	LIBS += -pthread
endif

# Add gtest to library if running unittest
ifeq (test,$(MAKECMDGOALS))
	LIBS += $(GTEST_LIBS) -lgtest -lgtest_main -pthread
	CXXFLAGS += -I./tests
	INCS += -Itests $(GTEST_INCS) $(LIBOMP_INCS)
endif

#---------------COMPILER SETUP

# Only run this logic if NOT on Darwin (macOS)
ifneq ($(UNAME_S), Darwin)
    ifeq ($(GCC),0)
        CC      = g++
        MPCC    = mpicxx
        CFLAGS  = -O3
        PROF    = -pg -g
    endif

    ifeq ($(INTEL),0)
        CC      = icpc
        MPCC    = mpicxx
        CFLAGS  = -O3
        PROF    = -pg -g
    endif
endif

# Ensure CXX always follows CC
CXX = $(CC)

#---------------OBJECT FILES

ifeq ($(OS),Linux)
       _OBJS = $(shell find $(SDIR) -name "*.cpp" | xargs -n 1 basename | sed -r 's/(\.cc|.cpp)/.o/')
else
       _OBJS = $(shell find $(SDIR) -name "*.cpp" | xargs -n 1 basename | sed -E 's/(\.cc|.cpp)/.o/')
endif

        OBJS = $(patsubst %,$(ODIR)/%,$(_OBJS))


#---------------RULES

syntax:
	@echo "------------------------------------"
	@printf '\033[31m%s\033[0m\n' "   USAGE: make serial|mpi|omp"
	@echo "------------------------------------"
	exit 0

#             Rules: for $(MAKECMDGOALS)  serial,     mpi, or            omp            build 
#                        $(EXEC)          bin/continuum_membrane, bin/continuum_membrane_mpi or /bincontinuum_membrane_omp
# Build the executable with or without tests

NON_CUDA_GOALS := $(filter-out $(CUDA_BACKEND_DIAGNOSTIC_GOALS),$(MAKECMDGOALS))
ifneq ($(strip $(NON_CUDA_GOALS)),)
$(NON_CUDA_GOALS):$(EXEC)
	@echo "Finished making (re-)building $@ version, $(EXEC)."
endif

$(EXEC): $(OBJS) $(TEST_OBJ)
	@echo "Linking $@"
	$(CXX) $(CFLAGS) $(CXXFLAGS) $(INCS) $(PROF) $(LDFLAGS) -o $@ $(EDIR)/$(@F).cpp $(OBJS) $(PLANG) $(LIBS)


$(ODIR)/%.o: %.cpp
	@echo "Compiling $< at $(<F) $(<D)"
	$(CXX) $(CFLAGS) $(CXXFLAGS) $(INCS) $(PROF) -c $< -o $@ $(PLANG) $(DEFS)

# Explicit Step-1 CUDA backend diagnostics. These targets are never
# prerequisites of serial, OpenMP, dynamics, test, or the default syntax goal.
CUDA_NVCC ?= nvcc
CUDA_HOST_CXX ?= $(CXX)
CUDA_COMPUTE_ARCH ?= compute_89
CUDA_SM_CODE ?= sm_89
CUDA_BACKEND_REPORT = $(BDIR)/cuda_backend_report
CUDA_BACKEND_STUB_REPORT = $(BDIR)/cuda_backend_stub_report
CUDA_MESH_STATE_REPORT = $(BDIR)/cuda_mesh_state_report
CUDA_MESH_STATE_STUB_REPORT = $(BDIR)/cuda_mesh_state_stub_report

.PHONY: cuda_backend_report cuda_backend_stub_report \
	cuda_mesh_state_report cuda_mesh_state_stub_report

cuda_backend_report: include/cuda/Cuda_backend.hpp \
		src/cuda/Cuda_backend_common.cpp src/cuda/Cuda_backend.cu \
		EXEs/cuda_backend_report.cpp
	@command -v $(CUDA_NVCC) >/dev/null 2>&1 || \
		( echo "CUDA_NVCC=$(CUDA_NVCC) was not found; this target is optional." >&2; exit 1 )
	$(CUDA_NVCC) -std=$(CXX_STD) -O3 \
		-arch=$(CUDA_COMPUTE_ARCH) -code=$(CUDA_SM_CODE) \
		-ccbin=$(CUDA_HOST_CXX) -Iinclude \
		src/cuda/Cuda_backend_common.cpp src/cuda/Cuda_backend.cu \
		EXEs/cuda_backend_report.cpp \
		-lcuda -o $(CUDA_BACKEND_REPORT)
	@echo "Finished optional CUDA backend report build, $(CUDA_BACKEND_REPORT)."

cuda_backend_stub_report: include/cuda/Cuda_backend.hpp \
		src/cuda/Cuda_backend_common.cpp src/cuda/Cuda_backend_stub.cpp \
		EXEs/cuda_backend_report.cpp
	$(CXX) -std=$(CXX_STD) -O3 -Iinclude \
		src/cuda/Cuda_backend_common.cpp src/cuda/Cuda_backend_stub.cpp \
		EXEs/cuda_backend_report.cpp -o $(CUDA_BACKEND_STUB_REPORT)
	@echo "Finished non-CUDA backend stub report build, $(CUDA_BACKEND_STUB_REPORT)."

# Explicit Step-3 persistent device-state diagnostics. The CUDA and stub
# implementations are mutually exclusive and remain outside every production
# or default target.
cuda_mesh_state_report: include/cuda/Cuda_mesh_state.hpp \
		include/cuda/detail/Cuda_mesh_state_core.hpp \
		src/cuda/Cuda_mesh_state_common.cpp src/cuda/Cuda_mesh_state.cu \
		EXEs/cuda_mesh_state_report.cpp
	@command -v $(CUDA_NVCC) >/dev/null 2>&1 || \
		( echo "CUDA_NVCC=$(CUDA_NVCC) was not found; this target is optional." >&2; exit 1 )
	$(CUDA_NVCC) -std=$(CXX_STD) -O3 \
		-arch=$(CUDA_COMPUTE_ARCH) -code=$(CUDA_SM_CODE) \
		-ccbin=$(CUDA_HOST_CXX) -Iinclude \
		src/cuda/Cuda_mesh_state_common.cpp src/cuda/Cuda_mesh_state.cu \
		EXEs/cuda_mesh_state_report.cpp \
		-lcudart -o $(CUDA_MESH_STATE_REPORT)
	@echo "Finished optional CUDA mesh-state report build, $(CUDA_MESH_STATE_REPORT)."

cuda_mesh_state_stub_report: include/cuda/Cuda_mesh_state.hpp \
		src/cuda/Cuda_mesh_state_common.cpp src/cuda/Cuda_mesh_state_stub.cpp \
		EXEs/cuda_mesh_state_report.cpp
	$(CXX) -std=$(CXX_STD) -O3 -Iinclude \
		src/cuda/Cuda_mesh_state_common.cpp src/cuda/Cuda_mesh_state_stub.cpp \
		EXEs/cuda_mesh_state_report.cpp -o $(CUDA_MESH_STATE_STUB_REPORT)
	@echo "Finished non-CUDA mesh-state stub report build, $(CUDA_MESH_STATE_STUB_REPORT)."


clean:
	rm -rf $(ODIR) bin
	rm -rf *.gcno *.gcda *.gcov coverage/ coverage.info

# Reference: https://www.gnu.org/software/make/manual/html_node/Quick-Reference.html
#            https://www.gnu.org/software/make/
#            https://www.cmcrossroads.com/article/basics-vpath-and-vpath
#            https://www.gnu.org/software/make/manual/html_node/Implicit-Variables.html
