"""This module is responsible for starting CORE (COncurrent REpair).

Configurations are held within the config.py module.

Copyright ARC, David Kelk and Kevin Jalbert, 2012
          ARC, CORE, David Kelk, 2013
"""

import os
import os.path
import shutil
import fileinput

# Convenience code
# Make sure config._ROOT_DIR is set correctly.  This is a problem
# when CORE is run on different machines at the same time.
coreDir = os.path.split(os.getcwd())[0] + os.sep
srcConfig = os.path.join("..", "input", "config.py")
if os.path.exists(srcConfig):
  configRoot = fileinput.FileInput(files=(srcConfig), inplace=1)
  for line in configRoot:
    if line.find("_ROOT_DIR =") is 0:
      line = "_ROOT_DIR = \"{}\" ".format(coreDir)
    print(line[0:-1]) # Remove extra newlines (a trailing-space must exists in modified lines)
  configRoot.close()

# Look for input/config.py and copy it to src so it doesn't
# have to be done manually every time
  if os.path.exists("config.py"):
    os.remove("config.py")
  if os.path.exists("config.pyc"):
    os.remove("config.pyc")
  shutil.copy(srcConfig, ".")

import config
import argparse
import subprocess
import tempfile
import re
import sys
from _contest import contester
from _evolution import evolution
from _txl import txl_operator
from _evolution import static
# Send2Trash from https://pypi.python.org/pypi/Send2Trash
from send2trash import send2trash

import logging
logger = logging.getLogger('core')

_OS = "MAC"

def main():
  """CORE starts here.

  Arguments
    Your soul
  Returns
    Eternal damnation (Or a PhD)
  """

  global _OS

  # Check for the workarea directory
  if not os.path.exists(config._PROJECT_DIR):
    os.makedirs(config._PROJECT_DIR)

  # Different operating systems implement some commands differently, so we
  # have to plan for that as it comes up. So far, we've found that MAC and
  # LINUX implement the time command differently. Therefore, determine which
  # OS we're running on.
  outFile = tempfile.SpooledTemporaryFile()
  errFile = tempfile.SpooledTemporaryFile()
  helpProcess = subprocess.Popen(['uname', '-o'], stdout=outFile, stderr=errFile,
    cwd=config._PROJECT_DIR, shell=False)
  helpProcess.wait()
  outFile.seek(0)
  outText = outFile.read()
  outFile.close()
  ourOS = 0 # 10 is Mac, 20 is Linux
  if re.search("Linux", outText):
    _OS = "LINUX"
  else:
    _OS = "MAC"

  # Compile the project
  if os.path.exists(config._PROJECT_DIR):
    shutil.rmtree(config._PROJECT_DIR)
  shutil.copytree(config._PROJECT_PRISTINE_DIR, config._PROJECT_DIR)

  txl_operator.compile_project()

  # Set up ConTest (Thread noising tool)
  contester.setup()
  # Set up Chord (A static analysis tool)
  static.setup()

  # Acquire classpath dynamically using 'ant test'
  if config._PROJECT_CLASSPATH is None:
    outFile = tempfile.SpooledTemporaryFile()
    errFile = tempfile.SpooledTemporaryFile()
    antProcess = subprocess.Popen(['ant', '-v', config._PROJECT_TEST],
                 stdout=outFile, stderr=errFile, cwd=config._PROJECT_DIR,
                 shell=False)
    antProcess.wait()
    outFile.seek(0)
    outText = outFile.read()
    outFile.close()

    # If you are getting an error at the re.search below, make sure the ant
    # build file (build.xml) has the following sections. _PROJECT_PRISTINE_SRC_DIR
    # and related entries in config.py have to agree with what is in the ant file:

    # <path id="classpath.base">
    #   <pathelement location="${current}" />
    #   <pathelement location="${build.classes}" />
    #   <pathelement location="${src.main}" />
    # </path>
    # <path id="classpath.test">
    #   <pathelement location="../lib/junit-4.8.1.jar" />
    #   <pathelement location="${tst-dir}" />
    #   <path refid="classpath.base" />
    # </path>

    # <target name="test" depends="compile" >
    #   <junit fork="yes">

    #       <!-- THE TEST SUITE FILE-->
    #       <test name = "Cache4jTest"/>

    #       <!-- NEED TO BE THE CLASS FILES (NOT ABSOLUTE) -->
    #       <classpath refid="classpath.test"/>
    #       <formatter type="plain" usefile="false" /> <!-- to screen -->
    #   </junit>
    # </target>

    config._PROJECT_CLASSPATH = re.search("-classpath'\s*\[junit\]\s*'(.*)'",
      outText).groups()[0]

  # Acquire dynamic timeout value from ConTest
  # CORE still uses ConTest, so this stays.
  contestTime = contester.run_test_execution(20)
  config._CONTEST_TIMEOUT_SEC = contestTime * config._CONTEST_TIMEOUT_MULTIPLIER
  logger.info("Using a timeout value of {}s".format(config._CONTEST_TIMEOUT_SEC))

  # Clean up the temporary directory (Probably has subdirs from previous runs)
  logger.info("Cleaning TMP directory")
  # Cleaning up a previous run could take half an hour on the mac
  # (10,000+ files is slow)
  # Trying an alternate approach: Sending the files to the trash
  # Using an external module, Send2Trash from:
  # https://pypi.python.org/pypi/Send2Trash
  # Install command: pip install Send2Trash
  # Some info on pip at: https://pypi.python.org/pypi

  if not os.path.exists(config._TMP_DIR):
    os.makedirs(config._TMP_DIR)
  else:
    send2trash(config._TMP_DIR)
    os.makedirs(config._TMP_DIR)


  # We're keeping a database (config file) containing the results
  # of previous static analysis runs. Check it first.
  if not static.find_static_in_db(config._PROJECT_TESTSUITE):
    static.configure_chord()
    static.run_chord_datarace()
    static.get_chord_targets()
    static.load_contest_list()

  # Primitive types (int, float, ...) cannot be locked on
  static.eliminate_primitives()
  static.create_final_triple()

  # Write the discovered values to file right away. The
  # final values are written in the finally block of
  # evolution.start() at the end of the run.
  if len(static._classVar) > 0 or len(static._classMeth) > 0 \
    or len(static._classMethVar) > 0:
    static.write_static_to_db(config._PROJECT_TESTSUITE)

  # Start the main bug-fixing procedure
  evolution.start()

# If this module is ran as main
if __name__ == '__main__':

  # Define the argument options to be parsed
  parser = argparse.ArgumentParser(
    description="CORE: Concurrent Repair of Java Programs "\
                  "<https://github.com/sqrg-uoit/core>",
    version="CORE 0.9.0",
    usage="python core.py")

  # Parse the arguments passed from the shell
  options = parser.parse_args()

  main()