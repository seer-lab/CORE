"""This module manages configuring and running JPF on the buggy program.
The buggy program requires a <project>.jpf configuration file.


Copyright David Kelk, 2013
"""

# TODO: Someone with a better knowledge of py4j and sockets should clean up this
#       code so the starting up and shutting down of the python side and the
#       Java side of the connection is done correctly. (See shutdownGateway())

# py4j is a library for calling java methods from python
# http://py4j.sourceforge.net/
from py4j.java_gateway import JavaGateway
import sys
sys.path.append("..")  # To allow importing parent directory module
import config
import subprocess
import tempfile
import re
import time
import logging
logger = logging.getLogger('core')

# Global variables

pyGateway = None
javaServer = None
jpfLauncher = None


def runJPF():
  """Create the JPF instance, configure it, invoke it and wait for the
  results.

  Returns:
    No return value
  """

  global pyGateway
  global javaServer
  global jpfLauncher

  # Compile and run the Java end of the gateway

  outFile = tempfile.SpooledTemporaryFile()
  errFile = tempfile.SpooledTemporaryFile()

  # Compile src/_jpf/launchJPF.java, which creates and runs the JPF session
  logger.debug("Compiling _jpf/launchJPF.java.")
  process = subprocess.Popen(['javac', '-cp', ".:" + config._JPF_JAR + ":" +
    config._PY4J_JAR, 'launchJPF.java'], stdout=outFile,
    stderr=errFile, cwd=config._JPF_DIR, shell=False)
  process.wait()

  # Paranoia: Kill any existing 'Java side of the bridge' instances
  #           See shutdownGateway() below
  process2 = subprocess.Popen(['kill', '`lsof -i TCP:25333`'], stdout=outFile,
    stderr=errFile, cwd=config._JPF_DIR, shell=False)
  process2.wait()

  outFile = tempfile.SpooledTemporaryFile()
  errFile = tempfile.SpooledTemporaryFile()

  logger.debug("Starting the Java side of the bridge.")
  # Run/start src/_jpf/launchJPF.java so we can connect to it throught py4j
  process3 = subprocess.Popen(['java', '-Xmx{}m'.format(config._PROJECT_TEST_MB),
    '-cp', ".:" + config._JPF_JAR + ":" + config._PY4J_JAR, 'launchJPF'],
    stdout=outFile, stderr=errFile, cwd=config._JPF_DIR, shell=False)
  time.sleep(2) # Wouldn't it be ironic if this lead to a data race

  # Create the local part of the gateway and connect to the Java end

  # auto_convert automatically converts python lists to java lists
  logger.debug("Creating the python side of the bridge.")
  pyGateway = JavaGateway(auto_convert=True)

  jpfLauncher = pyGateway.entry_point.getJPFInstance()

  # Create the configuration list for JPF. Note that we are creating a Java
  # array (of Strings), not a Python list

  # Note: Trying to create JPF objects by specifying them as a parameter
  #       here (eg: listener+= gov.nasa...BudgetChecker) doesn't work.
  #       Instead, create them in the launchJPF.java class and add them
  #       to JPF there. (See BudgetChecker as an example.)

  jpfConfig = pyGateway.new_array(pyGateway.jvm.java.lang.String, 6)
  jpfConfig[0] = config._JPF_CONFIG  # The .jpf file
  jpfConfig[1] = '+classpath=' + config._PROJECT_CLASS_DIR
  jpfConfig[2] = '+sourcepath=' + config._PROJECT_SRC_DIR
  jpfConfig[3] = 'search.class = gov.nasa.jpf.search.BFSearch'
  jpfConfig[4] = 'search.depth_limit = ' + str(config._JPF_SEARCH_DEPTH)
  jpfConfig[5] = 'budget.max_time = ' + str(config._JPF_SEARCH_TIME_SEC * 1000)

  # Invoke JPF through the gateway
  logger.debug("Running JPF throught the bridge.")
  jpfLauncher.resetJPF()
  jpfLauncher.setArgs(jpfConfig)
  jpfLauncher.runJPF()

  # Debugging
  # outFile.seek(0)
  # errFile.seek(0)
  # output = outFile.read()
  # error = errFile.read()
  # outFile.close()
  # errFile.close()
  # logger.debug("JPF Run, Output text:\n")
  # logger.debug(output)
  # logger.debug("JPF Run, Error text:\n")
  # logger.debug(error)

  # Wait for JPF to complete
  logger.debug("Waiting for JPF to complete.")
  while jpfLauncher.hasJPFRun() == False:
     time.sleep(1)


def shutdownGateway():
  """Shut down both the local and remote ends of the py4j connection.

  Returns:
    No return value
  """

  global pyGateway
  global javaServer

  logger.debug("Shutting down the gateway.")

  # Close the remote end/Java side
  # I've not been able to figure out how to close down the Java side of the
  # py4j gateway. A command-line way to do so is, kill `lsof -i TCP:25333`.
  # This kills any process listening on port 25333, the default used by py4j.
  # Killing the process isn't the right way to do it. Sadly, its the only
  # way I know how, so far.
  process = subprocess.Popen(['kill', '`lsof -i TCP:25333`'], stdout=outFile,
    stderr=errFile, cwd=config._JPF_DIR, shell=False)

  # Close the local end/python side
  if pyGateway is not None:
    pyGateway.close()


def analyzeJPFRace():
  """When JPF detects a datarace, the message looks similar to this

  Thread-1 at Account.transfer(pc 17)
   : putfield
  Thread-2 at Account.depsite(pc 2)
   : getfield

  Returns
    raceTuples (list (class, method) tuples): List of classes and methods
      involved in the data race.
      eg: [(Account, transfer), (Account, depsite)]
  """

  global jpfLauncher

  jpfRaceStr = jpfLauncher.getDataRaceErrorMessage()
  raceTuples = []

  if jpfRaceStr == None:
    return raceTuples

  if  jpfRaceStr.find("putfield") < 0 and jpfRaceStr.find("getfield") < 0:
    return raceTuples

  # Look for class.method
  for i in range(1, 3): # Assuming 3 threads at most involved
    race = re.search("(\S+)\.(\S+)\((\S+)", jpfRaceStr)
    if race is not None:
      aClass = race.group(1)
      aMeth = race.group(2)
      if aClass is not None and aMeth is not None:
        aTuple = (aClass, aMeth)
        if aTuple not in raceTuples:
          raceTuples.append(aTuple)

    # Remove the class.method that was just found from the string
    if ("Thread-" in jpfRaceStr):
      jpfRaceStr =  jpfRaceStr.split("Thread-",1)[1]

  return raceTuples


def analyzeJPFDeadlock():
  """When JPF detects a deadlock, the error message looks like

  gov.nasa.jpf.vm.NotDeadlockedProperty
  Error 0 Details:
  deadlock encountered:
  thread DiningPhil$Philosopher:{id:1,name:Thread-1,status:BLOCKED,priority:5,\
    lockCount:0,suspendCount:0}
  thread DiningPhil$Philosopher:{id:2,name:Thread-2,status:BLOCKED,priority:5,\
    lockCount:0,suspendCount:0}

  Returns
    lockList (list string): List of classes involved in the deadlock
                            eg: ('DiningPhil', 'Philosopher')
  """

  global jpfLauncher

  jpfDeadlockStr = jpfLauncher.getDeadlockErrorMessage()
  lockList = []

  if jpfDeadlockStr == None:
    return lockList

  if  jpfDeadlockStr.find("NotDeadlockedProperty") < 0 and jpfDeadlockStr.find("status:BLOCKED") < 0:
    return lockList

  # Look for classes
  for i in range(1, 5):
    lock = re.search("(\S+)\$(\S+):\{", jpfDeadlockStr)
    if lock is not None:
      aClass1 = lock.group(1)
      aClass2 = lock.group(2)
      if aClass1 not in lockList:
        lockList.append(aClass1)
      if aClass2 not in lockList:
        lockList.append(aClass2)

    # Remove the class.method that was just found from the string
    if ("suspendCount" in jpfDeadlockStr):
      jpfDeadlockStr =  jpfDeadlockStr.split("suspendCount",1)[1]

  return lockList


def getStatistics():
  """ Return some useful information about the JPF run.
  Java returns an ArrayList<long> which py4j converts to
  a python list. Values at index x correspond to:

    0 = max search depth,
    1 = # visited states,
    2 = # end states,
    3 = instructions executed,
    4 = max memory used

  Returns
    (list long): Statistics for the JPF run.
  """

  global jpfLauncher

  # py4j handles turning java's list<long> into a python list. see
  # http://py4j.sourceforge.net/getting_started.html#collections-help-and-constructors
  return jpfLauncher.getStatistics()


def timeExceeded():
  """ Did we run out of time? That is, did the search take longer than
  config._JPF_SEARCH_TIME_SEC seconds?

  Returns
    (boolean): Did we run out of time?
  """
  global jpfLauncher

  return jpfLauncher.timeExceeded()


def depthLimitReached():
  """ Did we reach the depth limit of config.JPF_SEARCH_DEPTH?

  Returns:
    (boolean): Did we reach the depth limit?
  """

  global jpfLauncher

  return jpfLauncher.depthLimitReached()