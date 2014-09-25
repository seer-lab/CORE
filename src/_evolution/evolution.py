"""This module starts the evolution process for CORE.

Copyright ARC, David Kelk and Kevin Jalbert, 2012
          ARC, CORE, CORE-INC, David Kelk, 2013
"""

from __future__ import division
import random
import sys
import os
from individual import Individual
import math
import traceback
import copy
from collections import Counter
sys.path.append("..")  # To allow importing parent directory module
import config
from _contest import tester
from _txl import txl_operator
import hashlist
import static
from py4j.java_gateway import JavaGateway
from _jpf import run_jpf
from send2trash import send2trash
import logging


logger = logging.getLogger('output-log')

# Set random's seed
if config._RANDOM_SEED is None:
  seed = random.randint(0, sys.maxint)
  logger.info("RANDOM SEED = {}".format(seed))
  random.seed(seed)
else:
  logger.info("RANDOM SEED = {}".format(config._RANDOM_SEED))
  random.seed(config._RANDOM_SEED)


# Global population to avoid passing it around
_population = []

# Global FunctionalPhase to avoid passing it around
_functionalPhase = True

# Are we still using JPF in the evalutation
_useJPF = True

def initialize(bestIndividual=None):
  """Initialize the population of individuals for either the functional or
  Optimization phases of the fixing process.  This function is called at
  most twice in a fixing run.

  Attributes:
    bestIndividual (individual): The fixed individual found in the first/
      functional phase. It is copied to all members of the population for
      the second/non-functional phase

  """

  global _population
  global _functionalPhase


  setOfOperators = GetMutationSet()

  _population = []  # Reset population for the Optimization phase

  # The number of enabled mutation operators
  mutationOperators = 0
  for operator in setOfOperators:
    if operator[1]:
      mutationOperators += 1

  # Create and initialize the population of individuals
  for i in xrange(1, config._EVOLUTION_POPULATION + 1):

    if bestIndividual is None:  # Functional phase
      #logger.debug("Creating individual {}".format(i))
      individual = Individual(mutationOperators, i)
    else:  # Non-functional phase
      logger.debug("Cloning repaired individual {} into individual {}".format(
                   bestIndividual.id, i))
      individual = bestIndividual.clone(mutationOperators, i)

    _population.append(individual)


def start():
  """The actual starting process for CORE's evolutionary process.
  """

  global _population
  global _functionalPhase

  try:
    # Initialize the population
    logger.info("Creating and initializing the population")
    initialize()

    # Start phase 1, the bug fixing phase
    logger.info("****************************")
    logger.info("Starting phase 1: Bug Fixing")
    logger.info("****************************")
    bestFunctional, bestFunctionalGeneration = evolve(0)

    # Check to see if a fixed member/program was found in phase 1.
    # If so, proceed to phase 2, optimization.
    if bestFunctional.successes[-1]/config._CONTEST_RUNS == 1.0 and bestFunctional.validated:
      logger.info("*********************************")
      logger.info("Fixed individual found in phase 1")
      logger.info("*********************************")
      logger.info(bestFunctional)
      logger.info("")

      # Proceed with the optimization phase, if enabled
      if not config._ONLY_FUNCTIONAL:

        _functionalPhase = False
        bestFunctional.switchGeneration = bestFunctional.generation
        # Reinitialize the population with the best functional individual
        logger.debug("Preparing for phase 2, optimization")
        logger.debug("Repopulating with best individual {} at generation {}".format(
          bestFunctional.id, bestFunctional.generation))

        initialize(bestFunctional)
        # Copy the fixed source into all members
        for individual in _population:
          if individual.id is not bestFunctional.id:
            txl_operator.copy_local_project_a_to_b(bestFunctional.generation,
              bestFunctional.id, bestFunctional.generation, individual.id)

        # Acquire worst possible non-functional score for best individual.
        # Here "worst" is the average of a large number of executions of
        # the fixed, unoptimized program
        txl_operator.move_local_project_to_workarea(bestFunctional.generation,
                                                    bestFunctional.id)
        txl_operator.compile_project()
        logger.debug("Acquiring Non-Functional worst score")
        contest = tester.Tester()
        contest.begin_testing(False, False, config._CONTEST_RUNS *
          config._CONTEST_VALIDATION_MULTIPLIER)  # Measure performance
        worstScore = get_average_non_functional_score(contest, bestFunctional,
          config._CONTEST_RUNS * config._CONTEST_VALIDATION_MULTIPLIER)

        # Evolve the population to find the best non-functional individual
        logger.info("******************************")
        logger.info("Starting Phase 2: Optimization")
        logger.info("******************************")
        bestOptimization, bestOptimizationGeneration = evolve(bestFunctional.generation,
                                                                worstScore)

        if bestOptimization is None:
          # It may be possible that the fixed program is too simple for any
          # optimizations to occur, or that no optimizations are found
          logger.info("**************************************************")
          logger.info("ERROR: No best individual was found during phase 2")
          logger.info("**************************************************")
          logger.info(bestOptimization)
          logger.info("")
        else:
          logger.info("*************************************")
          logger.info("Best individual found during phase 2:")
          logger.info("*************************************")
          logger.info(bestOptimization)
          logger.info("")

      # If phase 2 is disabled
      else:
        bestOptimization = bestFunctional
        bestOptimizationGeneration = bestFunctionalGeneration

      # Copy the fixed (And possibly optimized) project to the out dir
      logger.info("******************************************************")
      logger.info("Copying fixed project, Individual:{} Generation:{} to {}"
        .format(bestOptimization.id, bestOptimizationGeneration,
        config._PROJECT_OUTPUT_DIR))
      logger.info("******************************************************")
      txl_operator.move_best_project_to_output(bestOptimizationGeneration,
        bestOptimization.id)


    # Phase 1 didn't find a fix, so we don't start phase 2
    else:
      logger.info("No individual was found that functions correctly")

    # Debugging
    # logger.info("------------------------------")
    # logger.info("Here is the entire population:")
    # logger.info(_population)
    # logger.info("------------------------------")
    # logger.info("Note: Results of the run can be found before the listing \
    #    of the population.")
    # logger.info("(Scroll up)")

    # Notify the user if the solution found synchronizes run()
    # If so, let them know about the _EXCLUDE_RUN option
    outDir = os.path.join(config._PROJECT_OUTPUT_DIR,
      config._PROJECT_SRC_DIR.replace(config._PROJECT_DIR, ''))
    logger.debug("Checking if run was synchronized for the output project:")
    logger.debug("{}".format(outDir))
    if os.path.exists(outDir) and txl_operator.was_run_synchronized(outDir):
      logger.info("------------------------------------------------------")
      logger.info("Note that the solution found synchronizes run(). This ")
      logger.info("turned your (potentially fixed) program into a sequential")
      logger.info("one. There are two things you should consider doing:")
      logger.info("1. Consider re-designing your parallel code, or")
      logger.info("2. Use the `_EXCLUDE_RUN = True' option in config.py")
      logger.info("   to prevent CORE from synchronizing run in the future.")
      logger.info("------------------------------------------------------")

  except:
    logger.error("evolution.start: Unexpected error:\n", \
      traceback.print_exc(file=sys.stdout))
  finally:
    # Save the final results of the static analysis to file.  See
    # static.write_static_to_db for details.
    if len(static._classVar) > 0 or len(static._classMeth) > 0 \
      or len(static._classMethVar) > 0:
      static.write_static_to_db(config._PROJECT_TESTSUITE)
      logger.debug("Wrote static records to disk in section {}" \
        .format(config._PROJECT_TESTSUITE))

    # Delete all the remaining tmp\gen\mem\source directories
    for gen in xrange(1,config._EVOLUTION_GENERATIONS+1):
      for mem in xrange(1, config._EVOLUTION_POPULATION+1):
        sourceDir = os.path.join(config._TMP_DIR, str(gen), str(mem), "source")
        if os.path.isdir(sourceDir):
          send2trash(sourceDir)


def evolve(generation=0, worstScore=0):
  """This function is the workhorse for CORE: Both the fixing and
  optimization phases are run here.

  Attributes:
    generation (int): 0 for fixing phase, generation fix was found for
      the optimization phase
    worstScore (int?): TODO: Not used, linked to phase 2 fitness function

  Returns:
    individual (Individual): Best individual found for each phase, or None
  """

  global _population
  global _functionalPhase

  # Keeps track of the number of votes per mutation operator (improvements)
  dataraceVotes = {}
  deadlockVotes = {}
  OptimizationVotes = {}

  # For each generation, record the average and best fitness
  averageFitness = []
  bestFitness = []  # (score, id)

  # Each phase gets the full number of config._EVOLUTION_GENERATIONS to
  # work with
  if generation is 0:  # Fixing phase
    generationLimit = config._EVOLUTION_GENERATIONS
  else:  # Optimization phase
    generationLimit = config._EVOLUTION_GENERATIONS + generation

  while True:
    generation += 1

    # Mutate each individual
    moreMutations = False  # Does any member have mutations?
    highestSoFar = -1
    highestID = -1
    runningSum = 0

    for individual in _population:
      individual.generation = generation

      # Mutate an individual, then evaluate it right away
      # There are two circumstances under which false is returned:
      # - No mutants are generated for a member during the optimization phase
      # - No compilable project is generated for a member during the fixing phase
      # (If no mutants are found for a program during the fixing phase, an
      #  exception is raised in mutation.)
      mutationSuccess = mutation(individual, deadlockVotes, dataraceVotes,
                                 OptimizationVotes)

      if mutationSuccess:
        moreMutations = True
        evaluate(individual, generation)
        individual.wasRestarted.append(False)
        individual.wasReplaced.append(False)
        runningSum += individual.score[-1]
        if individual.score[-1] >= highestSoFar:
          highestSoFar = individual.score[-1]
          highestID = individual.id

        # Check to see if we can end the evolution process
        terminating, bestIndividual = terminate(individual, generation, generationLimit)
        if terminating:
          # We can, but the evolution process failed (eg, No fix found in phase 1)
          if bestIndividual is None:
            return get_best_individual()
          else:
            return bestIndividual, generation

      # No mutants were generate for a member of the population during the
      # Optimization phase, so we return the best individual found so far
      # TODO: I've forgotten the reason for this decision. We stop if only
      #       one member of the population doesn't have mutants.  Is that
      #       wise?
      elif not mutationSuccess and not _functionalPhase:
        logger.debug("No mutants were generated by member {} at generation {}.".format(individual.id, generation))
        logger.debug("Returning the best individual found so far.")
        return get_best_individual()

      # We can remove mutants for generation n-2. (We must keep generation n-1
      # for the restart case.) We do this as the mutants can take up a lot of
      # space.
      if individual.generation > 2:
        logger.debug("Cleaning up mutants for generation {} member {}."
          .format(individual.generation - 2, individual.id))
        txl_operator.clean_up_mutants(individual.generation - 2, individual.id)

    averageFitness.append(runningSum / config._EVOLUTION_POPULATION)
    bestFitness.append((highestSoFar, highestID))

    # Check for ending conditions

    # If the fitness doesn't improve over N generations during the
    # optimization phase, we stop
    if not _functionalPhase and convergence(generation, bestFitness, averageFitness):
      logger.debug("Returning the best individual found so far.")
      return get_best_individual()

    # No compilable projects were generated for any members during the fixing
    # phase.
    if not moreMutations:
      logger.info("No compilable projects were generated for any member of")
      logger.info("the population at generation {}. This is very odd.".format(generation))
      logger.info("Double-check that nothing has gone wrong with CORE.")
      return get_best_individual()

    # Update heuristics (Weighting, ...) if the search isn't random
    if not config._RANDOM_MUTATION:

      # If members of the population underperform for too long, we replace them
      # with either the
      # - pristine project (phase 1) or pristine fixed project (phase 2), or
      # - highest fitness project found in the phase so far
      replace_lowest(generation)

      # Perform mutation again for those individuals who were replaced or restarted
      for individual in _population:
        if generation == individual.generation - 1:
          mutationSuccessRestart = mutation(individual, deadlockVotes,
                                            dataraceVotes, OptimizationVotes)

          # If we are in the non-functional phase and a newly restarted member
          # doesn't generate any mutants, we stop
          # TODO: Same as above. During the optimization phase, why do we stop if
          #       only one member doesn't generate any mutants?
          if not _functionalPhase and not mutationSuccessRestart:
            logger.info("We restarted some underperforming members at generation {}.".format(generation))
            logger.info("No mutants could be generated for individual {}.".format(individual.id))
            logger.debug("Returning the best individual found so far.")
            return get_best_individual()

      # Adjust weighting of mutation operators
      deadlockVotes, dataraceVotes, OptimizationVotes = adjust_operator_weighting(generation)


def mutation(individual, deadlockVotes, dataraceVotes, OptimizationVotes):
  """A mutator for the individual using single mutation with feedback.

  Attributes:
    individual (Individual): Who we are scoring
    deadlockVotes, dataraceVotes, OptimizationVotes:
      Votes by operator type, eg: ({'ASAT': 1}) See the operator_weighting fn

  Returns:
    boolean:
      Functional phase: Was a compilable mutated project created for
        the individual?
      Optimization phase: Were any mutants created for the individual?
  """

  global _functionalPhase

  logger.info("-------------------------------------------------------------")
  logger.info("Mutating individual {} at generation {}".format(individual.id,
                                                        individual.generation))

  # Acquire set of operators to use
  mutationOperators = GetMutationSet()

  # Repopulate the individual's genome with new possible mutation locations
  # (Generates all mutations for the individual)
  totNumMutants = individual.repopulateGenome(_functionalPhase)

  # Check if individual has mutations
  # If no mutants exist, reset and re-attempt mutation
  if totNumMutants == 0:
    logger.debug("This individual didn't generate any mutants.")

    # For the optimization phase, we are done. Return the best indiviual
    # found so far (in evolve() above) and end the algorithm.
    if not _functionalPhase:
      return False

    # If we are in the fixing phase, we try to reset the project back to
    # the starting pristine one and generate mutants from it.
    txl_operator.create_local_project(individual.generation, individual.id, True)
    totNumMutants = individual.repopulateGenome(_functionalPhase)

    # Fixing phase: Check again for mutations
    # If mutants still don't exist, the pristine project has a problem
    if totNumMutants == 0:
      logger.error("Fixing phase: This individual had no mutants, so we replaced")
      logger.error("it with the original, pristine project. Somehow, no mutants")
      logger.error("were generated from the pristine project!. This is very odd.")
      logger.error("Check if CORE is operating correctly.")
      raise Exception("mutation fn, Fixing phase: Pristine project has no mutants")

  # If we reach this point, there are mutations, thus totNumMutants > 0

  # Hold attempted mutations, so we don't retry them
  # It is a set of sets by operator type
  # {{ASAT operators tried}, {ASIM operators tried}, ...}
  attemptedMutations = {}

  # Initialize attemptedMutations hash for valid operators
  operatorIndex = -1
  for mutationOp in mutationOperators:
    if mutationOp[1]:
      operatorIndex += 1
      attemptedMutations[operatorIndex] = set()

  # Big while loop where we try all mutants in turn
  outerLoopCtr = 0
  innerLoopCtr = 0      # Doesn't need to be declared here, but is :)
  totTriedMutants = 0
  retry = True
  while retry:

    # Make sure this loop doesn't go on forever. This is set quite high
    # to make sure an endless loop doesn't occur.
    # TODO: What happens if a project has more than 1000 mutations?
    #       - My first thought is that CORE has a slim chance of successfully
    #       fixing the bug with so many mutations available. Stopping at
    #       1000 isn't likely to worsen the (slim) chance of success.
    #       - There is also the matter of efficiency. Compiling projects
    #       takes time. Even at 1s per copy and compile, 1000 compiles
    #       would take 16.666 minutes.
    outerLoopCtr += 1
    if outerLoopCtr >= 1000:
      retry = False
      logger.debug("No compilable project found.")
      logger.debug("Exiting outer loop after {} iterations".format(outerLoopCtr))
      logger.debug("  This probably occurred because the remaining mutations were not")
      logger.debug("  compatible with what is trying to be fixed.  For example, if")
      logger.debug("  we are trying to fix data races, we don't remove synchronized")
      logger.debug("  blocks, so synchronization removing mutations are ignored.")
      break

    # Check if we have more mutants to try
    if totTriedMutants >= totNumMutants:
      # If not we jump down to the end of this function to deal with it
      retry = False
      break

    selectedOperator = feedback_selection(individual, deadlockVotes, dataraceVotes,
                                          OptimizationVotes)
    #logger.debug("Selected operator: {}".format(selectedOperator))

    # Find the integer index of the selectedOperator
    # That is, the index of ASAT, ASM, ...
    operatorIndex = -1
    for mutationOp in mutationOperators:
      if mutationOp[1]:
        operatorIndex += 1
        if mutationOp is selectedOperator:
          break

    # Look for a mutation we haven't tried yet, of the selected type
    if len(attemptedMutations[operatorIndex]) is len(individual.genome[operatorIndex]):
      continue

    # Untried mutations of the given type exist, so now we select one of them
    keepTrying = True
    innerLoopCtr = 0
    while keepTrying:
      # int
      randomMutant = random.randint(0, len(individual.genome[operatorIndex]) - 1)
      #logger.debug("Random mutant: {}".format(randomMutant))

      # Make sure we try a new mutation
      if randomMutant not in attemptedMutations[operatorIndex]:

        # Add mutation to set of attemptedMutations
        attemptedMutations[operatorIndex].add(randomMutant)
        keepTrying = False

      innerLoopCtr += 1

      if innerLoopCtr >= 1000:
        keepTrying = False
        logger.error("An untried {} mutant is supposed to exist.".format(selectedOperator))
        logger.error("We looked for it {} times, but couldn't find it.".format(innerLoopCtr))
        continue

    # When we get here, we have selected a new mutant to try
    totTriedMutants += 1

    # Now we check for reasons to exclude a mutant file:

    # 1. If we are excluding run as a synchronizable method, check the selected
    # mutant for it
    if hasattr(config, '_EXCLUDE_RUN'):
      if config._EXCLUDE_RUN:
        if txl_operator.check_synch_run(individual.generation, individual.id,
          selectedOperator[0], randomMutant + 1):
          continue

    # 2. Double locking on a variable isn't allowed:
    # removed the if...: for testing
    if txl_operator.check_double_synch(individual.generation, individual.id,
      selectedOperator[0], randomMutant + 1):
      continue

    # We wipe out the entire project and start again because we don't want
    # the previous mutation
    txl_operator.create_local_project(individual.generation, individual.id, False)
    txl_operator.move_mutant_to_local_project(individual.generation, individual.id,
                                              selectedOperator[0], randomMutant + 1)
    txl_operator.move_local_project_to_workarea(individual.generation, individual.id)
    #logger.debug("Attempting to compile...")

    if txl_operator.compile_project():
      #logger.debug("Success!")

      # Update individual with the successful operator type
      individual.lastOperator = selectedOperator
      individual.appliedOperators.append(selectedOperator[0])

      # Switch the appropriate bit to 1 to record which mutant is used
      individual.genome[operatorIndex][randomMutant] = 1

      #logger.debug("Selected operator for Individual {} at generation {}: {}, number {}".
      #  format(individual.id, individual.generation, selectedOperator[0], randomMutant + 1))
      return True
    # If the project didn't compile and we have retries left, go back to the start of the
    # while loop and try again

  # If we weren't able to compile a mutant project, reset it to the pristine and leave
  # it for this generation. We'll try again next generation to do something with it.
  logger.debug("Couldn't create a compilable mutant project. Resetting to the pristine \
                project (fixing phase) or best individual (optimization phase.)")
  if _functionalPhase:
    txl_operator.create_local_project(individual.generation, individual.id, True)
  else:
    txl_operator.create_local_project(individual.generation, individual.id,
                                  True, individual.switchGeneration + 1)

  # Update individual to reflect failed mutation
  individual.lastOperator = None
  individual.appliedOperators.append(None)

  return False


def feedback_selection(individual, deadlockVotes, dataraceVotes,
  OptimizationVotes):
  """Given the individual this function will find the next operator to apply.
  The operator selected will have generated mutants.

  The selection of the next operator takes into account the individual's last
  test execution as feedback. The feedback is used to heuristically guide what
  mutation operator to apply next. (More successful operators have a higher
  weighting and thus a larger chance of being selected.)

  Attributes:
    individual (Individual): Who we are scoring
    deadlockVotes, dataraceVotes, OptimizationVotes:
      Votes by operator type, eg: ({'ASAT': 1}) See the operator_weighting fn

  Returns:
    selectedOperator: One of ASAT, ASIM, ...
  """

  global _functionalPhase

  # candidateChoices is a list of config._MUTATIONS
  # { _MUTATION_ASAT, _MUTATION_ASIM, ...}
  candidateChoices = []

  # Acquire set of operators to use
  mutationOperators = GetMutationSet()


  # Case 1: Randomly choose an operator that has generated mutants
  if config._RANDOM_MUTATION:

    checkInd = -1
    for mutationOp in mutationOperators:
      if mutationOp[1]:
        checkInd += 1
        if len(individual.genome[checkInd]) > 0:
          candidateChoices.append(operator)

    # return an operator, eg: _MUTATION_ASIM
    return candidateChoices[random.randint(0,len(candidateChoices)-1)]

  # Case 2: Heuristic selection

  # 2.1. Acquire the deadlock and datarace rates
  # When the number of deadlocks and/or dataraces is 0, set the rates
  # to reasonable base values
  if len(individual.deadlocks) == 0 and len(individual.dataraces) == 0:
    deadlockRate = .5
    dataraceRate = .5
  elif len(individual.deadlocks) > 0 and len(individual.dataraces) == 0:
    deadlockRate = .8
    dataraceRate = .2
  elif len(individual.deadlocks) == 0 and len(individual.dataraces) > 0:
    deadlockRate = .2
    dataraceRate = .8
  else:
    deadlockRate = individual.deadlocks[-1] / config._CONTEST_RUNS
    dataraceRate = individual.dataraces[-1] / config._CONTEST_RUNS

  # Acquire a random value that is less then the total of the bug rates
  totalBugRate = (deadlockRate + dataraceRate)
  choice = random.uniform(0, totalBugRate)

  # 2.2. Determine which bug type to use. One of {'race', 'lock'}
  # TODO: Learn how to use enums (or equivalent) in python
  opType = 'race'
  if (dataraceRate > deadlockRate):
    # If choice falls past the datarace range then type is lock
    if choice > dataraceRate:
      opType = 'lock'
  else:
    # If choice falls under the deadlock range then type is lock
    if choice <= deadlockRate:
      opType = 'lock'

  # logger.debug("opType: {}".format(opType))

  # 2.3. Generate a list of operators that meet all the conditions
  #    (Used for races, enabled, generated mutants, ...)
  # From config.py:
  # Mutation operator variables
  # [0]Name  [1]Enable  [2]Enable for DataRace  [3]Enable for Deadlock  [4]File
  # [5] Functional phase: Use to fix DataRaces
  # [6] Functional phase: Use to fix Deadlocks
  # [7] Used in the non-functional phase
  # eg ['ASAT', True, True, True, _TXL_DIR + "ASAT.Txl", True, True, False]
  checkInd = -1
  for operator in mutationOperators:
    # Is it enabled globally
    if operator[1]:
      checkInd += 1
      # In the second/optimization phase, we don't worry about deadlocks and data
      # races. All enabled operators are used
      if not _functionalPhase and operator[7]:
        candidateChoices.append(operator)
      else:
        if opType is 'race':
          # Is it enabled for data races, does it have mutants and is it used
          # during the functional/fixing phase?
          if operator[2] and len(individual.genome[checkInd]) > 0 and operator[5]:
            candidateChoices.append(operator)


        elif opType is 'lock':
          if operator[3] and len(individual.genome[checkInd]) > 0 and operator[6]:
            candidateChoices.append(operator)
        else:
          logger.error('In the fixing phase, the operator types are {race, lock}.')
          logger.error(' Somehow an operator not in this set was selected.')

  # logger.debug("Before opChances candidateChoices: {}".format(candidateChoices))
  # logger.debug("                 deadlockVotes:    {}".format(deadlockVotes))
  # logger.debug("                 dataraceVotes:    {}".format(dataraceVotes))

  # 4. Acquire the operator chances based on what voting condition we have
  if _functionalPhase and opType is 'lock':
    operatorChances = get_operator_chances(candidateChoices, deadlockVotes)
    #logger.debug("Deadlock weighting: {}".format(operatorChances))
  elif _functionalPhase and opType is 'race':
    operatorChances = get_operator_chances(candidateChoices, dataraceVotes)
    #logger.debug("Datarace weighting: {}".format(operatorChances))
  else:
    operatorChances = get_operator_chances(candidateChoices, OptimizationVotes)
    #logger.debug("Operator chance for non-functional phase: {}".format(operatorChances))

  # 5. Select an operator based on the adjusted weighting

  # logger.debug("selection candidateChoices: {}".format(candidateChoices))
  # logger.debug("           operatorChances: {}".format(operatorChances))

  randomChance = random.randint(0,sum(operatorChances))
  currentRunning = 0  # Keeps track of sum (when we exceed this we are done)
  for i in xrange(len(operatorChances)):
    currentRunning += operatorChances[i]
    if randomChance <= currentRunning:
      selectedOperator = candidateChoices[i]
      break

  #logger.debug("Selected operator returned: {}".format(selectedOperator[0]))

  return selectedOperator


def get_operator_chances(candidateChoices, votes):
  """Score each operator based on how successful it is. For example,
  ASAT might get 5 points, ASIM 8 points, ...

  Attributes:
    candidateChoices: List of operators to weigh
    votes: Votes by operator type, eg: ({'ASAT': 1})
  Returns:
    operatorChances: Score of each operator, eg: ({'ASIM': 3})
  """

  # candidateChoices is a list of config._MUTATIONS
  # { [ASAT, True, ...], [ASIM, True, ...], ...}

  # votes is a list of tuples
  # eg {'ASIM': 1, 'ASAT': 1}

  #logger.debug("entry candidateChoices: {}".format(candidateChoices))
  #logger.debug("                 votes: {}".format(votes))

  # operator chances is the array of scores
  # eg: [5, 5, 0, 0]
  operatorChances = [0] * len(candidateChoices)
  currentValue = len(candidateChoices) + 1
  currentLarge = config._DYNAMIC_RANKING_WINDOW + 1

  # Map the values from largest to their appropriate values
  for op in sorted(votes, key=votes.get, reverse=True):

    # Move the currentValue down by one if the current votes are smaller
    if votes[op] < currentLarge:
      currentValue -= 1

    # Place the current value in the appropriate element for array of chances
    for i in xrange(len(candidateChoices)):
      if candidateChoices[i][0] == op:
        operatorChances[i] = currentValue
    currentLarge = votes[op]

    #logger.debug("Sorting candidateChoices {}".format(candidateChoices))
    #logger.debug("        operatorChances  {}".format(operatorChances))
    #logger.debug("        votes            {}".format(votes))

  # It is possible to have arrived here with operator chances being [0].
  # That is, there was only one applicable operator and it will be chosen
  # 0% of the time. Give each operator a weighting of atleast 1.
  for operator in operatorChances:
    if operator <= 0:
      operatorChances[operatorChances.index(operator)] = 1

  # Returns array of numbers, eg [3, 7, 2]
  #logger.debug("Returned operatorChances: {}".format(operatorChances))

  return operatorChances


def evaluate(individual, generation):
  """This method is a bit of a stub. Check if we've seen the mutant before.
  If so, re-use the testing results. If not, invoke JPF (or some other,
  future evalutation method) on it.

  Attributes:
    individual (Individual): Who we are scoring
  Returns:
    No return value
  """

  global _functionalPhase
  global _useJPF

  # If the mutant is a repeat, there is nothing more to do here
  seenBefore, hashVal = check_repeat_mutant(individual)
  if seenBefore:
    return

  # If the mutant isn't a repeat, add it to the hash list of seen
  # mutants and continue with the evaluation
  if hashVal != None and _functionalPhase:
    #logger.debug("Didn't find this mutated project hash in hash list: {}. \
    #  Adding it".format(hashVal))
    hashlist.add_hash(hashVal, individual.generation, individual.id)

  if _functionalPhase and _useJPF:
    TryContest = evaluate_modelcheck(individual, generation)
    if (TryContest):
      evaluate_contest(individual)
  else:
    evaluate_contest(individual)


def evaluate_modelcheck(individual, generation):
  """Determine the fitness of the individual using a model-checking
  approach with JPF (Java Pathfinder).

  Attributes:
    individual (Individual): Who we are scoring
  Returns:
    No return value
  """

  global _functionalPhase
  global _useJPF

  logger.info("Evaluating individual {}, generation {} with JPF".
    format(individual.id, individual.generation))

  try:
    logger.debug("Creating gateway.")
    run_jpf.createGateway(individual.id, generation)

    run_jpf.runJPF()

    # After running JPF, display any errors detected right away
    errStr = run_jpf.getErrorText()
    if errStr is not None and len(errStr) > 0:
      logger.debug("JPF error text:")
      logger.debug("{}".format(errStr))

    excStr = run_jpf.getExceptionText()
    if excStr is not None and len(excStr) > 0:
      logger.debug("JPF exception text:")
      logger.debug("{}".format(excStr))

    # Deal with specific problems
    if run_jpf.outOfMemory():
      logger.error("JPF ran out of memory. This mutant will be evaluated by ConTest.")
      return True

    if run_jpf.timeExceeded():
      logger.error("JPF ran out of time. This mutant will be evaluated by ConTest.")
      return True

    if not run_jpf.hasJPFRun():
      logger.error("Something has gone wrong. JPF hasn't run or hasn't completed")
      logger.error("running. This mutant will be evaluated by ConTest.")
      return True

    stats = run_jpf.getStatistics()
    if stats is None:
      logger.error("Something has gone wrong with JPF. No statistics were")
      logger.error("collected. This mutant will be evaluated by ConTest.")
      return True

    # Sometimes the stats array is full of 0s. Ie, the number of visited
    # states = 0, number of end states  = 0, etc...
    if stats[1] == 0 and stats[2] == 0:
      logger.error("JPF ran, but the statistics generated don't make sense.")
      logger.error("The number of visited states is 0. The number of end")
      logger.error("states is 0. This mutant will be evaluated by ConTest.")
      return True

    issueTxt = run_jpf.checkForKnownIssues()
    if issueTxt is not None and issueTxt is "attemptNullObjectLock":
      logger.error("We've generated a mutant that locks on an object before it")
      logger.error("is created. It compiles, but JPF will always report an")
      logger.error("\'Attempt to acquire lock for null object\' exception.")
      logger.error("Reseting this member so we can try again next generation.")
      txl_operator.create_local_project(individual.generation, individual.id, False)
      # Add scoring info for this generation (indexOutOfRange errors if you don't)
      individual.score.append(0)
      individual.evalMethod.append('None')
      individual.successes.append(-1)
      individual.timeouts.append(-1)
      individual.dataraces.append(-1)
      individual.deadlocks.append(-1)
      individual.errors.append(1)
      return False # No ConTest evaluation

    # Phew. We're past the error checking. Lets start the analysis.
    logger.debug("Statistics:")
    logger.debug("  Max search depth: {}".format(stats[0]))
    logger.debug("  # visited states: {}".format(stats[1]))
    logger.debug("  # end states: {}".format(stats[2]))
    logger.debug("  # instructions executed: {}".format(stats[3]))
    logger.debug("  Max memory used: {}".format(stats[4]))
    SearchDepth = stats[0]

    raceFound = run_jpf.wasADataraceFound()
    raceResult = run_jpf.getInfoInDatarace()
    if raceResult is not None:
      static.add_JPF_race_list(raceResult)
    logger.debug("Datarace found: {}".format(raceFound))
    logger.debug("Datarace data: {}".format(raceResult))

    lockFound = run_jpf.wasADeadlockFound()
    lockResult = run_jpf.getClassesInDeadlock()
    if lockResult is not None:
      static.add_JPF_lock_list(lockResult)
    logger.debug("Deadlock found: {}".format(lockFound))
    logger.debug("Deadlock data: {}".format(lockResult))

    depthLimitReached = stats[0] >= config._JPF_SEARCH_DEPTH
    logger.debug("Depth limit ({}) reached: {}".format( \
      config._JPF_SEARCH_DEPTH, depthLimitReached))

    maxFitness = config._CONTEST_RUNS * config._SUCCESS_WEIGHT
    logger.debug("Max fitness: {}".format(maxFitness))

    # Deep breath. If we've made it this far, we can attempt to make sense
    # of the results

    if depthLimitReached and (raceFound or lockFound):
      logger.debug("We've reached the configured depth limit, {}." \
        .format(config._JPF_SEARCH_DEPTH))
      logger.debug("Unfortunately there are still bugs. It looks like JPF")
      logger.debug("in its current configuration won't be able to help us")
      logger.debug("any more. Turning it off. For the rest of this run,")
      logger.debug("only ConTest will be used.")
      _useJPF = False
      return True

    if depthLimitReached and not raceFound and not lockFound:
      logger.debug("We've reached the configured depth limit, {}." \
        .format(config._JPF_SEARCH_DEPTH))
      logger.debug("No deadlocks or data races were reported, so we may have")
      logger.debug("a correct program. (To this depth.) Invoking ConTest for")
      logger.debug("further testing.")
      return True

    if raceFound or lockFound:
      logger.debug("Deadlock and/or data race found at depth {} (out of {})." \
        .format(SearchDepth, config._JPF_SEARCH_DEPTH))
      depthFit = (SearchDepth / config._JPF_SEARCH_DEPTH) * maxFitness
      logger.debug("Assign fitness {} (out of {}) and move on.".format(depthFit, maxFitness))
      # Higher fitness is assigned for races/locks found at higher search depths
      # If error is found at depth 19, the max depth is 50 and max fitness is 1000,
      # the assigned fitness is (19 / 50) * 1000 = 380
      individual.score.append(depthFit)
      individual.evalMethod.append('JPF')
      individual.successes.append(-1)
      individual.timeouts.append(-1)
      if raceFound:
        individual.dataraces.append(1)
      else:
        individual.dataraces.append(-1)
      if lockFound:
        individual.deadlocks.append(1)
      else:
        individual.deadlocks.append(-1)
      individual.errors.append(-1)
      return False

    if run_jpf.didAnExceptionOccur():
      logger.debug("There was no datarace or deadlock detected. An exception")
      logger.debug("of a more general type was thrown though. We're scoring")
      logger.debug("this mutant on the depth reached {} (out of {})." \
        .format(SearchDepth, config._JPF_SEARCH_DEPTH))
      depthFit = (SearchDepth / config._JPF_SEARCH_DEPTH) * maxFitness
      logger.debug("Assign fitness {} (out of {}) and move on.".format(depthFit, maxFitness))
      individual.score.append(depthFit)
      individual.evalMethod.append('JPF')
      individual.successes.append(-1)
      individual.timeouts.append(-1)
      individual.dataraces.append(-1)
      individual.deadlocks.append(-1)
      individual.errors.append(1)
      return False

    # Between this and "if raceFound or lockFound", all cases should be caught
    if not raceFound and not lockFound:
      logger.debug("No data races or deadlocks found at depth {} (out of {})"
        .format(SearchDepth, config._JPF_SEARCH_DEPTH))
      logger.debug("This program might be correct (?)")
      logger.debug("This mutant will be evaluated by ConTest.")
      return True

  except:
    logger.error("Encountered an exception calling evaluate_modelcheck:")
    excName, excValue = sys.exc_info()[:2]
    logger.error("{}".format(excName))
    logger.error("{}".format(excValue))
  finally:
    logger.debug("Shutting down JPF.")
    run_jpf.shutdownJPFProcess()

  logger.debug("We've reached the bottom of the evaluate_modelcheck function.")
  logger.debug("This mutant doesn't appear to have been evaluated yet.")
  logger.debug("It is being sent to ConTest.")
  return True


def evaluate_contest(individual):  #, worstScore):
  """Determine the fitness of the individual using a noising approach with
  ConTest.

  Attributes:
    individual (Individual): Who we are scoring
  Returns:
    No return value
  """

  global _functionalPhase

  # ConTest testing
  contest = tester.Tester()

  logger.info("Evaluating individual {}, generation {} with ConTest".
    format(individual.id, individual.generation))

  individual.evalMethod.append('ConTest')

  # Bug fixing phase
  if _functionalPhase:

    contest.begin_testing(_functionalPhase, False)

    # Fitness
    individual.score.append((contest.successes * config._SUCCESS_WEIGHT) + \
                            (contest.timeouts * config._TIMEOUT_WEIGHT))

    # Store results into genome
    individual.successes.append(contest.successes)
    individual.timeouts.append(contest.timeouts)
    individual.dataraces.append(contest.dataraces)
    individual.deadlocks.append(contest.deadlocks)
    individual.errors.append(contest.errors)


  # Optimization phase
  else:
    # Ensure functionality is still there
    if contest.begin_testing(_functionalPhase, True, config._CONTEST_RUNS *
      config._CONTEST_VALIDATION_MULTIPLIER):
      logger.debug("Optimization phase: Mutation didn't introduce any bugs")

      # Optimization fitness
      individual.score.append(get_average_non_functional_score(contest,
        individual, config._CONTEST_RUNS * config._CONTEST_VALIDATION_MULTIPLIER))
    else:
      logger.debug("Optimization phase: Mutation introduced a bug")
      individual.score.append(-1)

      # Need to ensure that the project from the last generation is used again
      # If we are on the first generation, we copy the pristine project from
      # config._PROJECT_PRISTINE_DIR, otherwise we use the project from the
      # previous generation

      # TODO: Double check that once the functional phase starts, the generation
      #       is reset to 1.

      if individual.generation - 1 is 0:
        logger.debug("Optimization phase: Resetting back to pristine")
        txl_operator.create_local_project(individual.generation, individual.id, True)
      else:
        logger.debug("Optimization phase: Resetting back to the previous generation")
        txl_operator.copy_local_project_a_to_b(individual.generation-1, individual.id,
                                               individual.generation, individual.id)
      individual.wasRestarted[-1] = True

  contest.clear_results()


def check_repeat_mutant(individual):
  """Check to see if this particular mutant has been seen before. If it has,
  we don't need to evaluate it again.  Simply copy the results from the
  first evaluation into this member.

  Attributes:
    individual (Individual): Who we are scoring
  Returns:
    Boolean: Has this mutant been seen before?
    String: Hash value or none
  """

  global _functionalPhase

  # TODO: Can this be used in the optimization phase too?
  if not _functionalPhase:
    return False, None

  # Check if we have encountered this mutant already
  md5Hash = hashlist.generate_hash(individual.generation, individual.id)
  if md5Hash is None:
    logger.error("Hash value of member {}, generation {} is NULL".format(
      individual.id, individual.generation))
    return False, None

  hashGen, hashMem =  hashlist.find_hash(md5Hash)
  if hashGen == None or hashMem == None:
    #logger.debug("Hash value of member {}, generation {} not found".format(
    #  individual.id, individual.generation))
    return False, md5Hash

  # If we have, we can skip the evaluation (saves time) and copy the testing
  # results from the first mutant
  #logger.debug("This is the same as generation {}, member {}.  Skipping \
  #  evaluation".format(hashGen, hashMem))
  prevIndvidual = _population[hashMem]

  #logger.debug("hashGen  : {}".format(hashGen))
  #logger.debug("Score    : {}".format(prevIndvidual.score))
  #logger.debug("Successes: {}".format(prevIndvidual.successes))
  #logger.debug("Timeouts : {}".format(prevIndvidual.timeouts))

  # Copy the testing information into the individual
  individual.score.append(prevIndvidual.score[-1])
  individual.successes.append(prevIndvidual.successes[-1])
  individual.timeouts.append(prevIndvidual.timeouts[-1])
  individual.dataraces.append(prevIndvidual.dataraces[-1])
  individual.deadlocks.append(prevIndvidual.deadlocks[-1])
  individual.errors.append(prevIndvidual.errors[-1])

  return True, md5Hash


def get_average_non_functional_score(contest, individual):
  """Calculate the non-functional score of the individual

  Precondition:
    contest.begin_testing should be called before so the test information is
      available
  Attributes:
    contest (Tester): Instance that did the testing in the Precondition
    individual (Individual): Who we are scoring
  Returns:
    avgFitness (int): Optimization fitness score
  """

  logger.info("Getting average non-functional score")

  # Get the average of realTime and voluntarySwitches
  avgRealTime = sum(contest.realTime, 0.0) / len(contest.realTime)
  avgVoluntarySwitches = sum(contest.voluntarySwitches, 0.0) / len(contest.voluntarySwitches)

  # Append average data to individual
  individual.realTime.append(avgRealTime)
  individual.voluntarySwitches.append(avgVoluntarySwitches)

  # Find the uncertainties in the measurements
  maxRT = max(contest.realTime)
  minRT = min(contest.realTime)
  maxVS = max(contest.voluntarySwitches)
  minVS = min(contest.voluntarySwitches)
  # Uncertainties in both
  uncRT = (maxRT - minRT) / avgRealTime
  uncVS = (maxVS - minVS) / avgVoluntarySwitches

  # Determine which one is more significant
  sigNum = 0.0
  sigUnc = 0.0
  otherNum = 0.0
  otherUnc = 0.0

  # Voluntary switches are more significant
  # TODO: In a real program, how do avgRealTime and avgVoluntarySwitches
  #       compare? Is one going to consistently be larger than the other?
  if (avgRealTime > avgVoluntarySwitches):
    sigNum = avgVoluntarySwitches
    sigUnc = uncVS
    otherNum = avgRealTime
    otherUnc = uncRT
  # Real time is most significant
  elif (avgRealTime < avgVoluntarySwitches):
    sigNum = avgRealTime
    sigUnc = uncRT
    otherNum = avgVoluntarySwitches
    otherUNC = uncVS
  else: # (avgRealTime == avgVoluntarySwitches):
    sigNum = 1
    sigUnc = uncVS
    otherNum = 1
    otherUnc = uncRT

  # Determine the fitness
  avgFitness = ((sigNum / otherNum) * (1 - sigUnc)) + ((otherNum/sigNum) * (1 - otherUnc))
  logger.debug("Optimization fitness: {}".format(avgFitness))
  contest.clear_results()
  return avgFitness


def adjust_operator_weighting(generation):
  """During different stages of the GAnotC, different operators may be more
  successful.  Look back config._DYNAMIC_RANKING_WINDOW generations to
  score how successful we have been at fixing data races and deadlocks
  with the different operators.

  Attributes:
    generation (int): Current generation
  Returns:
    deadlockVotes, dataraceVotes, OptimizationVotes:
      Votes by operator type, eg: ({'ASAT': 1})
  """

  global _population
  global _functionalPhase

  # Hashes of operator_name -> votes
  deadlockVotes = Counter()
  dataraceVotes = Counter()
  OptimizationVotes = Counter()

  # Consider that we are not pass the minimum sliding window value
  if generation <= config._DYNAMIC_RANKING_WINDOW:
    beginningGeneration = 1
  else:
    beginningGeneration = generation - config._DYNAMIC_RANKING_WINDOW

  logger.debug("Operator weighting window of generations {} to {}".format(
              beginningGeneration, generation))

  for individual in _population:

    # To ensure that the window will not cross back into the functional phase
    # TODO: This should be outside the loop? (Switch generation same for all)
    if beginningGeneration < individual.switchGeneration:
      logger.debug("Adjusting weighting window to not cross into functional phase")
      beginningGeneration = individual.switchGeneration

    # Only weight operators for valid mutations (ignore failed mutations)
    if individual.lastOperator is None:
      continue

    # Different members will have .deadlock and .datarace arrays of different
    # lengths. For example, member 1 might have [3, 5, 1] while member 2
    # might have [2, 1]
    upperBound = 0
    if _functionalPhase:
      if len(individual.deadlocks) < generation:
        upperBound = len(individual.deadlocks) - 1
      else:
        upperBound = generation - 1
    else: # Optimization
      if len(individual.score) < generation:
        upperBound = len(individual.score) - 1
      else:
        upperBound = generation - 1

    # TODO: This approach rewards a decrease in deadlocks multiple times.
    #       For example, if the window width is 10 and a member has 12
    #       deadlocks on generation 14 and 8 deadlocks on generation 15,
    #       it will accumulate 10 deadlock points as it moves through the
    #       window - one each turn.
    #       Is this desireable?
    logger.debug("beginningGeneration, {} should be <= upperBound, {}".format(beginningGeneration, upperBound))
    for i in xrange(beginningGeneration, upperBound):

      #logger.debug("individual.deadlocks: {}".format(individual.deadlocks))
      #logger.debug("individual.dataraces: {}".format(individual.dataraces))

      # Figure if there was any improvement from the last generation
      if _functionalPhase:
        if individual.deadlocks[i+1] < individual.deadlocks[i]:
          logger.debug("Deadlock improvement from individual {} in generation {}".
            format(individual.id, i))
          deadlockVotes[individual.appliedOperators[i]] += 1

          #logger.debug("deadlockVotes: {}".format(deadlockVotes))

        if individual.dataraces[i+1] < individual.dataraces[i]:
          logger.debug("Datarace improvement from individual {} in generation {}".
            format(individual.id, i))
          dataraceVotes[individual.appliedOperators[i]] += 1

          #logger.debug("dataraceVotes: {}".format(dataraceVotes))

      else: # Optimization phase
        if individual.score[i+1] > individual.score[i]:
          logger.debug("Non-functional improvement over individual {} in generation {}".
            format(individual.id, i))
          OptimizationVotes[i] += 1

  logger.debug("Deadlock Votes: {}".format(deadlockVotes))
  logger.debug("Datarace Votes: {}".format(dataraceVotes))
  logger.debug("Non-Functional Votes: {}".format(OptimizationVotes))

  return deadlockVotes, dataraceVotes, OptimizationVotes


def convergence(generation, bestFitness, averageFitness):
  """The population could stagnate. That is, there is no (or little)
  improvement in fitness over config._GENERATIONAL_IMPROVEMENT_WINDOW
  generations. If this is the case, there is a low chance of the
  algorithm working, so we stop early.

  Attributes:
    generation (int): Current generation
    bestFitness (list of int): Highest fitness score in population,
      per generation
    averageFitness(list of int): Average fitness of population, per
      generation
  Returns:
    boolean: Do we stop?
  """

  avgFitTest = False
  maxFitTest = False

  # Acquire the last N fitness values. The two variables are list of
  # numbers.
  windowAverageValues = averageFitness[-config._GENERATIONAL_IMPROVEMENT_WINDOW:]
  windowMaximumValues = bestFitness[-config._GENERATIONAL_IMPROVEMENT_WINDOW:]

  # if less than config._GENERATIONAL_IMPROVEMENT_WINDOW generations have
  # passed, we do nothing

  if len(windowAverageValues) == config._GENERATIONAL_IMPROVEMENT_WINDOW:
    if max(windowAverageValues) - min(windowAverageValues) > \
      config._AVG_FITNESS_MIN_DELTA:
      avgFitTest = True
    if max(windowMaximumValues, key=lambda x:x[0])[0] - min(windowMaximumValues,
        key=lambda x:x[0])[0] > config._BEST_FITNESS_MIN_DELTA:
      maxFitTest = True

    if not avgFitTest:
      logger.info("Average fitness hasn't moved by {} in {} generations".
            format(config._AVG_FITNESS_MIN_DELTA,
            config._GENERATIONAL_IMPROVEMENT_WINDOW))
      return True

    if not maxFitTest:
      logger.info("Maximum fitness hasn't moved by {} in {} generations".
            format(config._BEST_FITNESS_MIN_DELTA,
            config._GENERATIONAL_IMPROVEMENT_WINDOW))
      return True

  return False


def terminate(individual, generation, generationLimit):
  """Check to see if we should stop the fixing phase of the algorithm,
  because a correct program has been found.

  Attributes:
    generation (int): Current generation
    generationLimit (int): Max number of generations allotted
  Returns:
    boolean:    Do we stop?
    individual: Correct individual, or None if it still has bugs
  """

  global _population
  global _functionalPhase

  # If an proposed fix/individual passes the base number of tests
  if _functionalPhase and individual.successes[-1]/config._CONTEST_RUNS == 1:
    logger.info("Found potential best individual {}".format(individual.id))

    # ... and the individual passes the extended number of tests, we have
    # found a fix for the dataraces(s) and deadlock(s)
    if tester.Tester().begin_testing(True, True, config._CONTEST_RUNS
      * config._CONTEST_VALIDATION_MULTIPLIER):
      tester.Tester().clear_results()
      logger.info("Found best individual {}".format(individual.id))
      individual.validated = True
      return True, individual
    else:
      tester.Tester().clear_results()
      logger.info("Potential best individual still has errors")

  # We're out of generations
  if generation == generationLimit:
    logger.info("Exhausted all generations")
    return True, None

  # We still have generations left, so keep going
  return False, None


def get_best_individual():
  """Return the highest scoring individual.

  Returns:
    individual: Highest scorer, or None
    generation: Generation where high score occurs, or 0
  """

  global _population
  global _functionalPhase

  bestScore = -2
  bestIndividual = None
  generation = -1

  for individual in _population:
    # Determine the upper bound for xrange below
    # It can be shorter than expected for restarted members, say
    upperBound = 0
    if len(individual.score) < individual.generation:
      upperBound = len(individual.score) - 1
    else:
      upperBound = individual.generation - 1

    for i in xrange(0, upperBound):
      if individual.score[i] > bestScore:
        bestIndividual = individual
        generation = i + 1
        bestScore = individual.score[i]

  if bestIndividual is not None:
    return bestIndividual, generation
  else:
    return None, 0


def replace_lowest(generation):
  """Attempt to replace underperforming members with high-performing members or
  the original buggy program.

  Attributes:
    generation (int): Current generation of the GAnotC

  Returns:
    No return arguments
  """

  global _population
  global _functionalPhase

  # Determine the number of members to look at for underperforming
  numUnder = int((config._EVOLUTION_POPULATION
    * config._EVOLUTION_REPLACE_LOWEST_PERCENT)/100)
  if numUnder < 1:
    #numUnder = 1
    return

  # Sort population by fitness
  sortedMembers = sorted(_population, key=lambda individual: individual.score[-1])

  # The way this is coded, a member doesn't have to underperform on
  # consecutive generations to be replaced.  For example, if it underperformed
  # on generations 1, 5, 7 and 9 it would qualify for replacement (if #turns
  # is 5)
  # The first numUnder members have their turnsUnderperforming variable
  # incremented as they are the worst performing
  for i in xrange(0, numUnder):
    sortedMembers[i].turnsUnderperforming += 1

  # Check to see if we can replace the weakest individuals
  if generation % config._EVOLUTION_REPLACE_INTERVAL is not 0:
    # Sort the population by ID again and return
    _population = sorted(sortedMembers, key=lambda individual: individual.id)
    return

  logger.debug("Performing replacement of weakest {} individuals".format(numUnder))

  # Acquire set of operators to use
  mutationOperators = GetMutationSet()

  # Replace or restart members who have underperformed for too long
  for i in xrange(0, numUnder):

    if (sortedMembers[i].turnsUnderperforming < config._EVOLUTION_REPLACE_WEAK_MIN_TURNS):
      continue
    else:
      sortedMembers[i].turnsUnderperforming = 0

    randomNum = random.randint(1, 100)

    # Case 1: Replace an underperforming member with a fit member
    if randomNum <= config._EVOLUTION_REPLACE_WITH_BEST_PERCENT:

      # Check population size first
      if config._EVOLUTION_POPULATION * 0.1 < 1:
        logger.debug("Population size of {} is too small to take the top 10 percent from".format(config._EVOLUTION_POPULATION))
        return

      while True:
        # Take a member from the top 10% of the population
        # eg randint(27-29) for population size 30
        highMember =  random.randint(int(config._EVOLUTION_POPULATION * 0.9),
                          config._EVOLUTION_POPULATION) - 1

        # Ensure that the selected memeber is not the current member
        if highMember is not i:
          break

      logger.debug("Case 1: Replacing a low performer with a high performer")
      # Keep the id of the original member
      lowId = sortedMembers[i].id
      # logger.debug( "[INFO] Replacing ID: {} with {}".format(lowId, sortedMembers[highMember].id)
      sortedMembers[i] = copy.deepcopy(sortedMembers[highMember])
      sortedMembers[i].id = lowId
      sortedMembers[i].wasReplaced[-1] = True

      txl_operator.copy_local_project_a_to_b(sortedMembers[i].generation,
        sortedMembers[highMember].id, sortedMembers[i].generation, sortedMembers[i].id)

    # Case 2: Restart the member
    else:
      # The number of enabled mutation operators
      numOfOperators = 0
      for operator in mutationOperators:
        if operator[1]:
          numOfOperators += 1

      # logger.debug("[INFO] Restarting underperforming member ID: {}".format(sortedMembers[i].id)
      # TODO We don't know in the timeline, when an individual is restarted
      # If in functional restart off of local, otherwise off of best individual
      sortedMembers[i].wasRestarted[-1] = True
      if _functionalPhase:
        # Reset the local project to it's pristine state
        logger.debug("Case 2a: Reseting member {} generation {} back to the pristine project".
          format(sortedMembers[i].id, sortedMembers[i].generation))
        txl_operator.create_local_project(sortedMembers[i].generation,
          sortedMembers[i].id, True)
      else:
        # Reset to best individual
        logger.debug("Case 2b: Reseting member {} generation {} back to the original fixed project".
          format(sortedMembers[i].id, sortedMembers[i].generation))
        txl_operator.copy_local_project_a_to_b(sortedMembers[i].switchGeneration,
          sortedMembers[i].id, sortedMembers[i].generation, sortedMembers[i].id)

    # ALTERNATIVE: Reset the turnsUnderperforming at each interval
    # sortedMembers[i].turnsUnderperforming = 0

  # Resort the population by ID and reassign it to the original variable
  _population = sorted(sortedMembers, key=lambda individual: individual.id)


def GetMutationSet():
  """Return a list of mutant operators. For example,

  [['ASAT', True, True, True, _TXL_DIR + "ASAT.Txl", True, True],
   [True, True, True, _TXL_DIR + "ASIM.Txl", True, True], ...]

  Returns:
    List(MutantOperators)
  """

  global _functionalPhase

  if config._RANDOM_MUTATION:
    return config._ALL_MUTATIONS
  elif _functionalPhase:
    return  config._FUNCTIONAL_MUTATIONS
  else:
    return config._NONFUNCTIONAL_MUTATIONS
