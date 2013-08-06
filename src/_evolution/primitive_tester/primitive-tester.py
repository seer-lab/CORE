# The Static.search_files_for_primitives(primTuple) function has regular
# expressions in it to search for Java primitive types (int, float, ...).
# This test program exists to make sure the regular expressions correctly
# find only primitive variables.
# Only ints are looked for here. static.py contains the proper cut-n-paste
# for all primitive types.
#
# The java files in this directory are the test cases used.

import os
import re

_passed = 0
_failed = 0

def SearchPrimitives(sourceFile, argument, isPrimitive):

  global _passed
  global _failed

  with open(sourceFile) as f:
    lines = f.read().splitlines()

  isPrimitiveTest = False
  for line in lines:
    # Preprocessing
    # Strip out comments
    if line.find("//"):
      line = line[:line.find("//")]

    # Searches for int (varname)
    if re.search("int (" + argument + ")(?!\[)(?!\.)", line) is not None:
      print "  Case 1: " + line
      isPrimitiveTest = True
    if re.search("int (.*) (" + argument + ")(?!\[)(?!\.)", line) is not None:
      print "  Case 2: " + line
      isPrimitiveTest = True


  if isPrimitive == isPrimitiveTest:
    print "      Test passed"
    _passed += 1
  else:
    print "      Test FAILED"
    _failed += 1

  print "----------"

print "Account_Account: Random is NOT primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Account.java", "random", False)
print "Account_Account: MAX_SUM is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Account.java", "MAX_SUM", True)
print "Account_Account: Balance is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Account.java", "Balance", True)
print "Account_Account: Account_Id is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Account.java", "Account_Id", True)
print "Account_Account: sum is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Account.java", "sum", True)
print "Account_Account: loop is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Account.java", "loop", True)

print "Account_Bank: Bank_Total is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Bank.java", "Bank_Total", True)
print "Account_Bank: NUM_ACCOUNTS is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Bank.java", "NUM_ACCOUNTS", True)
print "Account_Account: accounts is NOT primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Bank.java", "accounts", False)
print "Account_Account: Bank_random is NOT primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Bank.java", "Bank_random", False)
print "Account_Account: out is NOT primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Account_Bank.java", "out", False)

print "Accounts_ManageAccount: account is NOT primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Accounts_ManageAccount.java", "account", False)
print "Accounts_ManageAccount: accounts is NOT primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/Accounts_ManageAccount.java", "accounts", False)

print "BubbleSort2_NewThread: array is NOT primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/BubbleSort2_NewThread.java", "array", False)
print "BubbleSort2_NewThread: fin is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/BubbleSort2_NewThread.java", "fin", True)
print "BubbleSort2_NewThread: priority is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/BubbleSort2_NewThread.java", "priority", True)
print "BubbleSort2_NewThread: temp is primitive"
SearchPrimitives("/Users/kelk/workspace/tmp/BubbleSort2_NewThread.java", "temp", True)

print " "
print "Passed: {}".format(_passed)
print "Failed: {}".format(_failed)