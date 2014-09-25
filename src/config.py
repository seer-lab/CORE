"""This module holds all the configuration values that are used in ARC.

There are system, target project, ConTest, mutation operator and evolution
variables that are set in this file and are used all throughout ARC.
"""

import logging

# Worked when run by JPF directly
_USE_JPF = True
_EXCLUDE_RUN = True

# System variables
_ROOT_DIR = "/Users/kelk/workspace/CORE/"
_MAX_MEMORY_MB = 2000
_MAX_CORES = 2
_TMP_DIR = _ROOT_DIR + "tmp/"
_TXL_DIR = _ROOT_DIR + "src/_txl/"
_JPF_DIR = _ROOT_DIR + "src/_jpf/"
_JUNIT_JAR = _ROOT_DIR + "lib/junit-4.8.1.jar"
_LOG_LEVEL = "DEBUG"  # {OFF,ERROR,WARN,INFO,DEBUG}
_LOG_FILE = "log.txt"  # If None then use stdout, otherwise specify a file
_RANDOM_SEED = None  # None means use the system time, non-zero is fixed
_OS = "MAC"

# Target project variables

# Original project is placed in the input directory.
# Invariant: This directory _ROOT_DIR = "/Users/kelk/workspace/CORE/"is read-only
_PROJECT_PRISTINE_DIR = _ROOT_DIR + "input/"
_PROJECT_PRISTINE_SRC_DIR = _PROJECT_PRISTINE_DIR + "source/"

# Projects are compiled and tested in the workarea directory
_PROJECT_DIR = _ROOT_DIR + "workarea/"
_PROJECT_SRC_DIR = _PROJECT_DIR + "source/"
_PROJECT_TEST_DIR = _PROJECT_DIR + "test/"
_PROJECT_CLASS_DIR = _PROJECT_DIR + "class/"

# A fixed project (if found) is placed in the output directory
_PROJECT_OUTPUT_DIR = _ROOT_DIR + "output/"
_PROJECT_PREFIX = "Account,Main,Bank,BusinessAccount,Manager,PersonalAccount"  # Comma separated fully-qualifying class names or package prefixes
_PROJECT_TESTSUITE = "AccountSubTypeTest"
_PROJECT_COMPILE = "compile"
_PROJECT_TEST = "test"
_PROJECT_CLASSPATH = None  # Automatically acquired using ant test if None
_PROJECT_TEST_MB = 2000

# JPF variables
_JPF_JAR = _ROOT_DIR + "lib/JPF/build/jpf.jar"
_JPF_INCREMENTAL_JAR = _ROOT_DIR + "lib/JPF/build/jpf-incremental.jar"
_JPF_CONFIG = _PROJECT_PRISTINE_DIR + 'account.jpf'
_JPF_SEARCH_DEPTH = 50
_JPF_SEARCH_TIME_SEC = 30

# Location of py4j jar
_PY4J_JAR = _ROOT_DIR + "lib/Java/py4j0.8.jar"

# Chord variables - static analysis to find classes, methods and variables
# used concurrently
_CHORD_MAIN = "Main"
_CHORD_COMMAND_LINE_ARGS = "10 1"

_CHORD_DIR = _ROOT_DIR + "lib/Chord/"
_CHORD_PROPERTIES = _CHORD_DIR + "chord.properties"
_CHORD_JAR = _CHORD_DIR + "chord.jar"

# ConTest variables - keep these for finding shared classes and variables
_CONTEST_DIR = _ROOT_DIR + "lib/ConTest/"
_CONTEST_KINGPROPERTY = _CONTEST_DIR + "KingProperties"
_SHARED_VARS_FILE = _PROJECT_DIR + "com_ibm_contest/sharedVars.txt"
_CONTEST_JAR = _CONTEST_DIR + "ConTest.jar"
_CONTEST_RUNS = 10
_CONTEST_TIMEOUT_SEC = 300 # Default timeout, it is adjusted dynamically
# Default multiplier of 20 was too low for this program
_CONTEST_TIMEOUT_MULTIPLIER = 20  # The average execution time (with conTest) is multiplied by this
_CONTEST_VALIDATION_MULTIPLIER = 15  # Allows for validation of functionality

# Mutation operator variables
# [0]Name  [1]Enable  [2]Enable for DataRace  [3]Enable for Deadlock  [4]File
# [5] Functional phase: Use to fix DataRaces
# [6] Functional phase: Use to fix Deadlocks
_MUTATION_ASAT = ['ASAT', True, True, True, _TXL_DIR + "ASAT.Txl", True, True]
_MUTATION_ASIM = ['ASIM', True, True, True, _TXL_DIR + "ASIM.Txl", True, True]
_MUTATION_ASM  = ['ASM', True, True, True, _TXL_DIR + "ASM.Txl", True, True]
_MUTATION_CSO  = ['CSO', True, True, True, _TXL_DIR + "CSO.Txl", False, True]
_MUTATION_EXSB = ['EXSB', True, True, True, _TXL_DIR + "EXSB.Txl", True, True]
_MUTATION_EXSA = ['EXSA', True, True, True, _TXL_DIR + "EXSA.Txl", True, True]
_MUTATION_RSAS = ['RSAS', True, True, True, _TXL_DIR + "RSAS.Txl", False, True]
_MUTATION_RSAV = ['RSAV', True, True, True, _TXL_DIR + "RSAV.Txl", False, True]
_MUTATION_RSIM = ['RSIM', True, True, True, _TXL_DIR + "RSIM.Txl", False, True]
_MUTATION_RSM  = ['RSM', True, True, True, _TXL_DIR + "RSM.Txl", False, True]
_MUTATION_SHSA = ['SHSA', True, True, True, _TXL_DIR + "SHSA.Txl", False, True]
_MUTATION_SHSB = ['SHSB', True, True, True, _TXL_DIR + "SHSB.Txl", False, True]
_FUNCTIONAL_MUTATIONS = [_MUTATION_ASAT, _MUTATION_ASIM,
                         _MUTATION_ASM, _MUTATION_CSO, _MUTATION_EXSB,
                         _MUTATION_EXSA, _MUTATION_RSAS, _MUTATION_RSAV,
                         _MUTATION_RSIM, _MUTATION_RSM, _MUTATION_SHSA,
                         _MUTATION_SHSB]
_NONFUNCTIONAL_MUTATIONS = [_MUTATION_RSAS, _MUTATION_RSAV, _MUTATION_RSIM,
                            _MUTATION_RSM, _MUTATION_SHSA, _MUTATION_SHSB]
_ALL_MUTATIONS = [_MUTATION_ASAT, _MUTATION_ASIM,
                         _MUTATION_ASM, _MUTATION_CSO, _MUTATION_EXSB,
                         _MUTATION_EXSA, _MUTATION_RSAS, _MUTATION_RSAV,
                         _MUTATION_RSIM, _MUTATION_RSM, _MUTATION_SHSA,
                         _MUTATION_SHSB]

# Enable random mutation
_RANDOM_MUTATION = False

# Only perform functional phase
_ONLY_FUNCTIONAL = True

# Evolution variables
_EVOLUTION_GENERATIONS = 30
_EVOLUTION_POPULATION = 30
_EVOLUTION_REPLACE_LOWEST_PERCENT = 10
_EVOLUTION_REPLACE_INTERVAL = 5  # Consider replacement on this generational interval
_EVOLUTION_REPLACE_WEAK_MIN_TURNS = 3  # Min number of turns of underperforming before replacement
_EVOLUTION_REPLACE_WITH_BEST_PERCENT = 75

# Dynamic ranking window (number of generations to consider)
_DYNAMIC_RANKING_WINDOW = 5

# Fitness evaluation variables
_SUCCESS_WEIGHT = 100
_TIMEOUT_WEIGHT = 50

# Convergence criteria, considering the window size ensure there is at least
# a fitness score movement of delta
_GENERATIONAL_IMPROVEMENT_WINDOW = 10
_AVG_FITNESS_MIN_DELTA = 0.01
_BEST_FITNESS_MIN_DELTA = 1

# Create logger
logger = logging.getLogger('output-log')
if _LOG_FILE is None:
  handler = logging.StreamHandler()
else:
  handler = logging.FileHandler(_LOG_FILE, "w");

logger.setLevel(_LOG_LEVEL)

formatter = logging.Formatter('%(relativeCreated)d %(levelname)s [%(module)s.%(funcName)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
