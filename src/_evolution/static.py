""" Perform a static analysis of the source to be fixed to gain
information about the classes, methods and variables used
concurrently.

Currently Chord is used. This unit can be adapted to other static,
dynamic or other analysis tools as needed.

Copyright David Kelk, 2012-13
"""

import subprocess
import os
import os.path
import sys
sys.path.append("..")  # To allow importing parent directory module
import zipfile
import config
import re
import tempfile
import shutil
import fileinput
import sys
import urllib2
from bs4 import BeautifulSoup
import ConfigParser
import logging
logger = logging.getLogger('core')

# The targeting of classes, methods and variables for mutation can be
# improved by finding which ones are used concurrently. There are different
# tools that can do this - like Chord, a static analysis tool and ConTest,
# which we use for noising. Different tools return different information -
# like the Class and variable used concurrently or the class and variable
# used concurrently.
# This file contains methods to collect the classes, methods and variables
# found with the ultimate goal of producing a list of (class, method,
# variable) (c, m , v) triples.
# If the (c, m, v) information isn't available, we may still have (c, m)
# or (c, v) information to work with.

# TODO: Record the results of the static analysis so it doesn't have to
#       be run every time.

_contestFoundVars = False

classVar = []

classMeth = []

classMethVar = []


def setup():
  """Check if the directories and tools are present for the testing process."""

  try:
    logger.info("Checking for Chord")
    if (not os.path.exists(config._CHORD_JAR)):
      raise Exception('ERROR MISSING Chord TOOL', 'config._CHORD_JAR')

    logger.info("Checking for Chord's chord.properties")
    if (not os.path.exists(config._CHORD_PROPERTIES)):
      raise Exception('ERROR MISSING Chord CONFIGURATION', 'config._CHORD_PROPERTIES')
  except Exception as message:
    print (message.args)
    sys.exit()

# ------------------------ Chord ------------------------

def configure_chord():
  logger.info("Configuring Chord's chord.properties file")

  # Where we will place the properl configured chord.properties file (in input dir)
  chordLoc = config._PROJECT_DIR + 'chord.properties'

  if os.path.exists(chordLoc):
    os.remove(chordLoc)

  shutil.copy(config._CHORD_PROPERTIES, chordLoc)

  for line in fileinput.FileInput(chordLoc, inplace=1):
    if line.find("chord.class.path =") is 0:
      line = "chord.class.path = {} ".format(config._PROJECT_CLASS_DIR.replace(".", "/"))
    elif line.find("chord.src.path =") is 0:
      line = "chord.src.path = {} ".format(config._PROJECT_SRC_DIR)
    elif line.find("chord.main.class =") is 0:
      line = "chord.main.class = {} ".format(config._CHORD_MAIN)
    elif line.find("chord.args.0 =") is 0:
      line = "chord.args.0 = {} ".format(config._CHORD_COMMAND_LINE_ARGS)
    # For some reason the "e" of true is removed when the file is written to.  Add the space to stop it
    elif line.find("chord.print.results =") is 0:
      line = "chord.print.results = true "
    print(line[0:-1])  # Remove extra newlines


def run_chord_datarace():
  os.chdir(config._PROJECT_DIR)

  logger.info("Running Chord in datarace finding mode (This may take a while.)")

  outFile = tempfile.SpooledTemporaryFile()
  errFile = tempfile.SpooledTemporaryFile()

  # Chord is run by invoking the build.xml in Chord's dir. (lib\Chord\build.xml)
  process = subprocess.Popen(['ant', '-f', os.path.join(config._CHORD_DIR, 'build.xml') ,
    'run'], stdout=outFile, stderr=errFile, cwd=config._PROJECT_DIR, shell=False)

  process.wait()


def did_chord_find_dataraces():
  # core/workarea/chord_output
  chordOutDir = os.path.join(config._PROJECT_DIR, 'chord_output')

  if not os.path.exists(chordOutDir):
    logger.error("Chord output directory, {}, not found".format(chordOutDir))
    return False

  # core/workarea/chord_output/dataraces_by_fld.html
  URL = os.path.join(chordOutDir, 'dataraces_by_fld.html')

  if not os.path.isfile(URL):
    logger.error("Chord output file, {}, not found".format(URL))
    return False

  # Back up the file
  shutil.copy(URL, os.path.join(config._TMP_DIR, 'dataraces_by_fld.html'))

  # A HTML page with 0 data races in it is 1,174 bytes in size. (For Chord 2.1)
  # (Attempts to find deadlocks resulted in 500MB files which were unuseable.)
  if os.path.getsize(URL) < 1200:
    logger.info("Chord didn't detect any data races (Or didn't run correctly.)")
    return False

  logger.info("Chord found data races")
  return True


def get_chord_targets():
  if not did_chord_find_dataraces():
    return False

  chordOutDir = os.path.join(config._PROJECT_DIR, 'chord_output')
  URL = os.path.join(chordOutDir, 'dataraces_by_fld.html')
  URL = 'file:' + URL
  page = urllib2.urlopen(URL)
  data = page.read()

  # Use BeautifulSoup to analyze the web page produced by Chord
  soup = BeautifulSoup(data)

  for (i, row) in enumerate(soup("tr")):
    # First 3 rows of the table in dataraces_by_fld.html are header information
    if i <= 2:
      continue

    tds = row.findAll("td")
    tdTxt = ''.join(tds[0].findAll(text=True))

    # 1. Look for "Dataraces on ... classname.varname"
    # eg:  <tr>
    #        <td class="head3" colspan="5">1. Dataraces on
    #                  <a href="null.html#0">Account.Balance</a></td>
    #     </tr>
    if tdTxt.find("Dataraces on") > 0:
      # Look for class.variable
      stmtOne = re.search("(\S+)\.(\S+)", tdTxt)
      if stmtOne is None:
        continue
      aClass = stmtOne.group(1)
      aVar = stmtOne.group(2)
      if aClass is None or aVar is None:
        continue
      aTuple = (aClass, aVar)
      if aTuple not in classVar:
        logger.debug("(Case 1) Adding {} to classVar".format(aTuple))
        classVar.append(aTuple)

    # 2. Look for class.method(args), except for .main(java.lang.String[])
    # eg: <tr>
    #        <td><a href="race_TE0_TE1.html">1.1</a></td>
    #        <td><a href="null.html#-1">Account.run()</a></td>
    #        <td><a href="null.html#-1">Bank.Service(int,int)</a> (Wr)
    #        </td>
    #        <td><a href="null.html#-1">Bank.main(java.lang.String[])</a></td>
    #        <td><a href="null.html#-1">Bank.main(java.lang.String[])</a> (Rd)
    #        </td>
    #     </tr>
    elif tdTxt.find("race_TE") > 0:

      for j in range(1, 4):  # Always 4 tds
        tdStr = ''.join(tds[j].find(text=True))
        # Ignore anything containing ".main(java.lang.String[])"
        if tdStr.find(".main(java.lang.String[])") > 0:
          continue
        stmtTwo = re.search("(\S*)\.(\S*)\(\S*\)", tdStr)
        if stmtTwo is None:
          continue
        aClass = stmtTwo.group(1)
        aMeth = stmtTwo.group(2)
        if aClass is None or aMeth is None:
          continue
        aTuple = (aClass, aMeth)
        if aTuple not in classMeth:
          logger.debug("(Case 2) Adding {} to classMeth".format(aTuple))
          classMeth.append(aTuple)

  if len(classVar) > 0:
    logger.debug("Populated class.variable list with Chord data")
  if len(classMeth) > 0:
    logger.debug("Populated class.method list with Chord data")


# ----------------------- Utility -----------------------

def create_final_triple():
  if len(classMeth) == 0 or len(classVar) == 0:
    #logger.debug("Couldn't create the list of (class, method, variable) triples")
    #logger.debug("One or both of the static analysis and ConTest shared variable detection didn't")
    #logger.debug("find anything, or failed. As we are missing one (or both) of class.method and")
    #logger.debug("class.variable, config.finalCMV, the list of class-method-variable triples")
    #logger.debug("will be empty.")
    return False

  for cmTuple in classMeth:
    for cvTuple in classVar:
      if not cmTuple[-2] == cvTuple[-2]:  # Must be the same class
        continue
      aTriple = (cmTuple[-2], cmTuple[-1], cvTuple[-1]) # Class, method, variable
      if aTriple not in classMethVar:
        #logger.debug("Adding triple {} to finalCMV".format(aTriple))
        classMethVar.append(aTriple)

  #logger.info("Populated (class, method, variable) list with Chord and ConTest data")
  return True


def do_we_have_CV():
  return len(classVar) > 0


def do_we_have_CM():
  return len(classMeth) > 0


def do_we_have_CMV():
  return len(classMethVar) > 0

# -------------- ConTest Related Functions ---------------

def did_contest_find_shared_variables():
  # Ensure that there is a shared variable file (From ConTest)
  if not os.path.exists(config._SHARED_VARS_FILE):
    logger.error("ConTest's config._SHARED_VARS_FILE doesn't exist")
    return False

  # If you are concerned ConTest didn't run correctly, uncomment the
  # "logger.debug("==== Tester, Output text:\n")" section of lines in
  # tester.py
  if os.path.getsize(config._SHARED_VARS_FILE) == 0:
    logger.info("ConTest didn't detect any shared variables (Or didn't run correctly.)")
    return False

  return True


def load_contest_list():

  global _contestFoundVars

  if _contestFoundVars:
    return True

  if not did_contest_find_shared_variables():
    return False

  for line in open(config._SHARED_VARS_FILE, 'r'):
    variableName = line.split('.')[-1].strip(' \t\n\r')
    className = line.split('.')[-2].strip(' \t\n\r')
    aTuple = (className, variableName)
    if aTuple not in classVar:
      logger.debug("Adding {} to classVar".format(aTuple))
      classVar.append(aTuple)

  logger.info("Populated class.variable list with ConTest data")
  _contestFoundVars = True
  create_final_triple()
  return True

# ---------------- JPF Related Functions -----------------

def add_JPF_race_list(JPFlist):
  """Add the new (class, method) tuples discovered by JPF to
  the list of (class, method) tuples involved in the race or
  deadlock.

  Arguments:
    JPFList (List (class, method) tuples): Tuples discovered
      by JPF
  """

  for aTuple in JPFlist:
    if aTuple not in classMeth:
      classMeth.append(aTuple)

  create_final_triple()


def add_JPF_lock_list(JPFList):
  """Combine the list of classes involved with the deadlocks
  discovered by JPF with the methods already found in the
  classMeth tuples and adds them to classMeth.

  Arguments
    JPFList (List string): List of classes involved in deadlocks
  """

  for aItem in JPFList:
    for aTuple in classMeth:
      newTuple = (aItem, aTuple[1])
      if newTuple not in classMeth:
        classMeth.append(newTuple)

  create_final_triple()

# ------------- Database of Static Analysis -----------------

def find_static_in_db(projectName):
  """

  """

  dbFileIn = os.path.join(config._ROOT_DIR , "src", "staticDB.txt")
  if not os.path.exists(dbFileIn):
    open(dbFileIn, 'a').close()
    return False

  configDBIn = ConfigParser.ConfigParser()
  configDBIn.readfp(open(dbFileIn))

  if not configDBIn.has_section(projectName):
    return False

  classVar = configDBIn.get(projectName, "classVar")
  classMeth = configDBIn.get(projectName, "classMeth")
  classMethVar = configDBIn.get(projectName, "classMethVar")
  logger.debug("Read classVar : {}".format(classVar))
  logger.debug("Read classMeth: {}".format(classMeth))
  logger.debug("Read classMeVa: {}".format(classMethVar))

  #configDBIn.close()
  return True

def write_static_to_db(projectName):
  """

  """

  dbFileOut = os.path.join(config._ROOT_DIR , "src", "staticDB.txt")
  if not os.path.exists(dbFileOut):
    open(dbFileOut, 'a').close()

  inData = open(dbFileOut, 'r')
  configDBOut = ConfigParser.ConfigParser()
  configDBOut.read(inData)

  if not configDBOut.has_section(projectName):
    configDBOut.add_section(projectName)

  configDBOut.set(projectName, "classVar", classVar)
  configDBOut.set(projectName, "classMeth", classMeth)
  configDBOut.set(projectName, "classMethVar", classMethVar)

  outData = open(dbFileOut, 'w')
  configDBOut.write(outData)
