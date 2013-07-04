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
logger = logging.getLogger('arc')


def runJPF():
  # Step 0: Compile and run the JPF gateway

  outFile = tempfile.SpooledTemporaryFile()
  errFile = tempfile.SpooledTemporaryFile()

  # Compile src/_jpf/launchJPF.java
  process = subprocess.Popen(['javac', '-cp', ".:" + config._JPF_JAR + ":" +
    config._PY4J_JAR, 'launchJPF.java'], stdout=outFile,
    stderr=errFile, cwd=config._JPF_DIR, shell=False)
  process.wait()

  outFile = tempfile.SpooledTemporaryFile()
  errFile = tempfile.SpooledTemporaryFile()

  # Run src/_jpf/launchJPF.java
  process = subprocess.Popen(['java', '-Xmx{}m'.format(config._PROJECT_TEST_MB),
    '-cp', ".:" +config._JPF_JAR + ":" + config._PY4J_JAR, 'launchJPF'],
    stdout=outFile, stderr=errFile, cwd=config._JPF_DIR, shell=False)
  time.sleep(2)

  outFile.seek(0)
  errFile.seek(0)
  output = outFile.read()
  error = errFile.read()
  outFile.close()
  errFile.close()
  logger.debug("Open gateway, Output text:\n")
  logger.debug(output)
  logger.debug("Open gateway, Error text:\n")
  logger.debug(error)

  # Step 1: Create the gateway to the java program and connect to it

  # auto_convert automatically converts python lists to java lists
  gateway = JavaGateway(auto_convert=True)

  jpfLogger = logging.getLogger("py4j")
  jpfLogger.setLevel(logging.DEBUG)
  jpfLogger.addHandler(logging.StreamHandler())

  jpfLauncher = gateway.entry_point.getJPFInstance()

  # Step 2: Create the necessary lists of configuration information for
  #         both py4j (to connect to launchJPF.java) and for the JPF
  #         project being run.

  # Create list of strings for configuring JPF
  # Note that we are creating a Java array, not a Python list

  jpfConfig = gateway.new_array(gateway.jvm.java.lang.String, 3)
  jpfConfig[0] = config._JPF_CONFIG
  jpfConfig[1] = '+classpath=' + config._PROJECT_CLASS_DIR
  jpfConfig[2] = '+sourcepath=' + config._PROJECT_SRC_DIR

  # Step 3: Invoke JPF through the gateway

  jpfLauncher.resetJPF()
  jpfLauncher.setArgs(jpfConfig)
  jpfLauncher.runJPF()

  while jpfLauncher.hasJPFRun() == False:
     time.sleep(1)

  # Step 4: Get the results of the JPF run

  resDataRace = jpfLauncher.getDataRaceErrorMessage()
  if resDataRace <> None:
    print("DataRace Results: " + resDataRace)

  resDeadlock = jpfLauncher.getDeadlockErrorMessage()
  if resDeadlock <> None:
    print("Deadlock Results: " + resDeadlock)

  # Get the more generic error messages
  #List<gov.nasa.jpf.Error>  jpfErr = jpf.getSearch().getErrors();
  #  System.out.println("Description:");
  #  System.out.println(jpfErr.get(0).getDescription());
  #  System.out.println("Details:");
  #  System.out.println(jpfErr.get(0).getDetails());
  if jpfLauncher.getErrorCount() > 0:
    for i in (0, jpfLauncher.getErrorCount() - 1):
      print("Error " + str(i) + " Description:")
      print(jpfLauncher.getErrorDescription(i))
      print("Error " + str(i) + " Details:")
      print(jpfLauncher.getErrorDetails(i))

  # Step 5: Shut down the py4j server

  gateway.shutdown()

  return resDataRace, resDeadlock


def analyzeJPFRace(jpfRaceStr):
  """When JPF detects a datarace, the message looks similar to this

   Thread-1 at Account.depsite(Account.java:7)
     "//constructor"  : putfield
   Thread-5 at Account.transfer(Account.java:12)
     "//functions"  : getfield

  returns a list of (class, method) tuples
  eg: [(Account, depsite)]
  """

  raceTuples = []

  if jpfRaceStr == None:
    return raceTuples

  # < 0 means not found
  if  jpfRaceStr.find("putfield") < 0 and jpfRaceStr.find("getfield") < 0:
    return raceTuples

  # Look for class.method
  for i in range(1, 3):
    race = re.search("(\S+)\.(\S+)\((\S+)\.(\S+)\:", jpfRaceStr)
    if race is not None:
      aClass = race.group(1)
      aMeth = race.group(2)
      if aClass is not None and aMeth is not None:
        aTuple = (aClass, aMeth)
        raceTuples.append(aTuple)

    # Remove the class.method that was just found from the string
    if ("//" in jpfRaceStr):
      jpfRaceStr =  jpfRaceStr.split("//")[1]

  return raceTuples

# TODO: Implement deadlock analysis fn

#def analyzeJPFDeadlock(jpfDeadlockStr):




raceStr, deadStr = runJPF()
raceList = analyzeJPFRace(raceStr)
print("Race list:")
print(raceList)
print("Deadlock:")
print(deadStr)