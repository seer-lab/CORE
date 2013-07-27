"""This module manages configuring and running JPF on the buggy program.
The buggy program requires a <project>.jpf configuration file.


Copyright David Kelk, 2013
"""


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
_jpfLauncher = None
_jpfProcess = None

def createGateway():
  # Compile and run the Java end of the gateway

  global _jpfProcess

  outFile = tempfile.SpooledTemporaryFile()
  errFile = tempfile.SpooledTemporaryFile()

  # Compile src/_jpf/launchJPF.java, which creates and runs the JPF session
  logger.debug("Compiling _jpf/launchJPF.java.")
  process = subprocess.Popen(['javac', '-cp', ".:" + config._JPF_JAR + ":" +
    config._PY4J_JAR, 'launchJPF.java'], stdout=outFile,
    stderr=errFile, cwd=config._JPF_DIR, shell=False)
  process.wait()

  # Debugging
  # outFile.seek(0)
  # errFile.seek(0)
  # output = outFile.read()
  # error = errFile.read()
  # outFile.close()
  # errFile.close()
  # logger.debug("Compile, Output text:\n")
  # logger.debug(output)
  # logger.debug("Compile, Error text:\n")
  # logger.debug(error)

  outFile = tempfile.SpooledTemporaryFile()
  errFile = tempfile.SpooledTemporaryFile()

  logger.debug("Starting the Java side of the bridge.")
  # Run/start src/_jpf/launchJPF.java so we can connect to it throught py4j
  _jpfProcess = subprocess.Popen(['java', '-Xmx{}m'.format(config._PROJECT_TEST_MB),
    '-cp', ".:" + config._JPF_JAR + ":" + config._PY4J_JAR, 'launchJPF'],
    stdout=outFile, stderr=errFile, cwd=config._JPF_DIR, shell=False)
  time.sleep(2) # Wouldn't it be ironic if this lead to a data race

  # Debugging
  outFile.seek(0)
  errFile.seek(0)
  output = outFile.read()
  error = errFile.read()
  outFile.close()
  errFile.close()
  logger.debug("JPF Run, Output text:\n")
  logger.debug(output)
  logger.debug("JPF Run, Error text:\n")
  logger.debug(error)


def runJPF(individualID, generation):
  """Create the JPF instance, configure it, invoke it and wait for the
  results.

  Returns:
    No return value
  """

  global _jpfLauncher

  # Create the local part of the gateway and connect to the Java end

  # auto_convert automatically converts python lists to java lists
  #logger.debug("Creating the python side of the bridge.")
  pyGateway = JavaGateway(auto_convert=True)

  _jpfLauncher = pyGateway.entry_point.getJPFInstance()

  # Create the configuration list for JPF. Note that we are creating a Java
  # array (of Strings), not a Python list

  # Note: Trying to create JPF objects by specifying them as a parameter
  #       here (eg: listener+= gov.nasa...BudgetChecker) doesn't work.
  #       Instead, create them in the launchJPF.java class and add them
  #       to JPF there. (See BudgetChecker as an example.)

  jpfConfig = pyGateway.new_array(pyGateway.jvm.java.lang.String, 9)
  jpfConfig[0] = config._JPF_CONFIG  # The .jpf file
  jpfConfig[1] = '+classpath=' + config._PROJECT_CLASS_DIR
  jpfConfig[2] = '+sourcepath=' + config._PROJECT_SRC_DIR
  jpfConfig[3] = 'search.class = gov.nasa.jpf.search.BFSearch'
  jpfConfig[4] = 'search.depth_limit = ' + str(config._JPF_SEARCH_DEPTH)
  jpfConfig[5] = 'budget.max_time = ' + str(config._JPF_SEARCH_TIME_SEC * 1000)
  jpfConfig[6] = 'log.level = info'
  jpfConfig[7] = 'log.output = JPFLog-test-do-i-exist-no-i-dont-why.txt'
  jpfConfig[8] = 'log.info = jpfLog' # Matches launchJPF.java

  #jpfConfig[7] = 'log.output = JPFLog-' + str(individualID) + '-' + str(generation) + '.txt'

  # Invoke JPF through the gateway
  logger.debug("Running JPF throught the bridge.")
  _jpfLauncher.resetJPF()
  _jpfLauncher.setArgs(jpfConfig)

  try:
    _jpfLauncher.runJPF()
  except:
    logger.error("Encountered an exception: {}".format(sys.exc_info()[0]))


def shutdownJPFProcess():

  global _jpfProcess

  _jpfProcess.send_signal(3)
  time.sleep(1)
  _jpfProcess.terminate()


def hasJPFRun():

  global _jpfLauncher

  return _jpfLauncher.hasJPFRun()


def wasADataraceFound():
  """Race messages can come from two places. The first is from the race
  object:

  Thread-1 at Account.transfer(pc 17)
   : putfield
  Thread-2 at Account.depsite(pc 2)
   : getfield

  The second is from the error text (why?):

  gov.nasa.jpf.listener.PreciseRaceDetector race for field NewThread.endd
    main at Loader.main(pc 135)
  "  : getstatic
    Thread-1 at NewThread.<init>(pc 24)
  "  : putstatic

  Returns
    None or raceTuples (list (class, method) tuples): List of classes and methods
      involved in the data race.
      eg: [(Account, transfer), (Account, depsite)]
  """

  global _jpfLauncher

  jpfRaceStr = _jpfLauncher.getDataRaceErrorMessage()
  if jpfRaceStr is not None and jpfRaceStr.find("putfield") > 0 \
    and jpfRaceStr.find("getfield") > 0 and \
    re.search("(\S+)\.(\S+)\((\S+)", jpfRaceStr) is not None:
    return True

  jpfErrStr = getErrorString()
  if jpfErrStr is not None and jpfErrStr.find("gov.nasa.jpf.listener.PreciseRaceDetector") > 0 \
    and re.search("(\S+)\.(\S+)\((\S+)", jpfErrStr) is not None:
    return True

  return False


def getInfoInDatarace():

  global _jpfLauncher

  if not wasADataraceFound():
    return None

  # Cheat: Since we know that one or both of the strings in wasADataRaceFound()
  # has races, concatenate the two together and search them both at once
  jpfRaceStr = _jpfLauncher.getDataRaceErrorMessage() + getErrorString()
  raceTuples = []

  if jpfRaceStr == None: # This shouldn't happen
    return None

  # Look for class.method
  for i in range(1, 6): # Arbitrary loop count
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
      jpfRaceStr =  jpfRaceStr.split("Thread-", 1)[1]

  return raceTuples


def wasADeadlockFound():
  """When JPF detects a deadlock, one of two messages may be returned. They are:

  gov.nasa.jpf.vm.NotDeadlockedProperty deadlock encountered:
  thread java.lang.Thread:{id:0,name:main,status:WAITING,priority:5,lockCount:0,suspendCount:0}
  thread java.lang.Thread:{id:1,name:0,status:BLOCKED,priority:5,lockCount:0,suspendCount:0}
  ...
  thread java.lang.Thread:{id:6,name:5,status:BLOCKED,priority:5,lockCount:0,suspendCount:0}
  thread java.lang.Thread:{id:7,name:6,status:TERMINATED,priority:5,lockCount:0,suspendCount:0}
  ...

  and

  gov.nasa.jpf.vm.NotDeadlockedProperty
  Error 0 Details:
  deadlock encountered:
  thread DiningPhil$Philosopher:{id:1,name:Thread-1,status:BLOCKED,priority:5,\
    lockCount:0,suspendCount:0}
  thread DiningPhil$Philosopher:{id:2,name:Thread-2,status:BLOCKED,priority:5,\
    lockCount:0,suspendCount:0}
  ...

  This function looks for the text string "NotDeadlockedProperty". In either of these
  messages.

  Returns
    deadlockFound (boolean): Was a deadlock found?
  """

  global _jpfLauncher

  jpfDeadlockStr = getErrorString()

  return jpfDeadlockStr.find("NotDeadlockedProperty") > 0


def getClassesInDeadlock():
  """The second deadlock text in wasADeadlockFound() contains the classes
  involved in the deadlock. (eg. DiningPhil$Philosopher) Extract them so
  CORE can target the search for a fix better.

  Returns
    None or lockList (list string): List of classes involved in the deadlock
                            eg: ('DiningPhil', 'Philosopher')
  """

  global _jpfLauncher

  jpfDeadlockStr = _jpfLauncher.getDeadlockErrorMessage()
  if jpfDeadlockStr == None:
    return None

  if  jpfDeadlockStr.find("NotDeadlockedProperty") < 0 and \
    re.search("(\S+)\$(\S+):\{", jpfDeadlockStr) is None:
    return None

  # Look for classes
  lockList = []
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
      jpfDeadlockStr =  jpfDeadlockStr.split("suspendCount", 1)[1]

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

  global _jpfLauncher

  # py4j handles turning java's list<long> into a python list. see
  # http://py4j.sourceforge.net/getting_started.html#collections-help-and-constructors
  return _jpfLauncher.getStatistics()


def getErrorString():

  global _jpfLauncher

  # Constructed in deadlock, passed back raw here
  return _jpfLauncher.getDeadlockErrorMessage()


def getExceptionText():

  global _jpfLauncher

  return _jpfLauncher.getExceptionText()


def timeExceeded():
  """ Did we run out of time? That is, did the search take longer than
  config._JPF_SEARCH_TIME_SEC seconds?

  Returns
    (boolean): Did we run out of time?
  """
  global _jpfLauncher

  return _jpfLauncher.timeExceeded()


def depthLimitReached():
  """ Did we reach the depth limit of config.JPF_SEARCH_DEPTH?

  Returns:
    (boolean): Did we reach the depth limit?
  """

  global _jpfLauncher

  return _jpfLauncher.depthLimitReached()


def outOfMemory():
  """ Did JPF crash with an out of memory error? There are multiple out of
  memory checks. Each one was put in after run_jpf.py, py4j or launchJPF.java
  reported an out of memory exception.

  Returns:
    (boolean): Did it?
  """

  global _jpfLauncher

  errStr = getErrorString()
  if errStr is not None and errStr.find("gov.nasa.jpf.vm.NoOutOfMemoryErrorProperty") > 0:
    return True

  excStr = getExceptionText()
  if excStr is not None and excStr.find("out-of-memory termination") > 0:
    return True
