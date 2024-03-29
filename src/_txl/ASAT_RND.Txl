%***********************************************************
% ASAT (Add Sync Around Statement) Mutator for ARC
% (Automatic Repair of Concurrency Bugs)
% No targeting info available so we hit everything (_RND)
%
% -syncvar: Synchronization variable - synchronized(syncvar)
%
% Copyright David Kelk and Kevin Jalbert, 2012
%           David Kelk, 2013
%
% Based on ASK by J.S. Bradbury
%
% Typical (eventual) invocation:
% txl ManageAccount.java ASAT.Txl - -outfile ManageAccount_1.java
% -outdir ASAT/ -syncvar coolness
%
% Notes:
% - Java files must be named _1.java, _2.java due to the fact
%   that the second invocation of mutant generation will
%   overwrite the first.
% - Output directory must already exist.
%***********************************************************

%***********************************************************
% ASK (Add Synchronized Keyword To a Method) Mutator
% Jeremy S. Bradbury

% Copyright 2006 J.S. Bradbury

% Description: This mutation operator adds the synchronized
% keyword to any method that is not synchronized. We do
% not consider constructors because a constructor method
% can not be synchronized.

% NOTE: This operator generates a number of equivalent
% mutants. In the future we plan to restrict the ASK mutator
% to add a synchronized modifier ONLY to methods that
% have synchronized blocks (with the objective to cause
% a deadlock bug)
%***********************************************************

% Base grammar, and grammar override files
include "Java.Grm"
include "JavaCommentOverrides.Grm"

% Local grammar overrides

redefine statement
        [sync_other_statement]
    |   [attr labelM] [other_statement]
end redefine

define other_statement
        [label_statement]
    |   [empty_statement]
    |   [expression_statement]
    |   [if_statement]
    |   [switch_statement]
    |   [while_statement]
    |   [do_statement]
    |   [for_statement]
    |   [break_statement]
    |   [continue_statement]
    |   [return_statement]
    |   [throw_statement]
    |   [synchronized_statement]
    |   [try_statement]
    |   [block]
end define

% How it looks after mutation
% - For parsing, labels are considered optional

define sync_other_statement
  [attr labelM] /* 'MUTANT: [stringlit] */  [NL]
  'synchronized '( [id] ')
  '{ [NL][IN]
    [other_statement] [EX]
  '}   [NL]
  /* 'MUTANT: [stringlit] */  [NL]
end define

define labelM
  'MUTATED
end define

%------------------------------------------------------------
% Main
% - Prepare import and export variables
%   - clsNm/className: Targeted class
%   - varNm/variableName: Targeted variable
%------------------------------------------------------------
function main
  % initialize and export a mutant count that will be used in
  % file name / folder name generation
  construct MutantCount [number]
    0
  export MutantCount

  % initialize and export the name of the current mutant which
  % will be used for folder name generation
  construct MutantOpName [stringlit]
    "ASAT_RND"
  export MutantOpName

  % Read in name of class and variable from ConTest
  import TXLargs [repeat stringlit]
    deconstruct * TXLargs
       "-syncvar" synVr [stringlit] MoreOptions [repeat stringlit]

  construct synchVar [id]
    _ [unquote synVr]
  export synchVar

  replace [program]
    P [program]
  by
    P [ProcessSynchronizeStatementMutations]
end function

%------------------------------------------------------------
% Start the mutation process at the global level.
% - IdentifyMutationClass limits the scope to the required
%   class (className)
% - The other classes are skipped over
% - Print/WriteToFile has to be at this level so that ALL
%   classes appear in the mutated file
%------------------------------------------------------------
rule ProcessSynchronizeStatementMutations
  replace [program]
    P [program]
  where
    P [?doSynchronizeStatementMutation]
  by
    P [doSynchronizeStatementMutation]
      %[print]
      [writeToFile]
      % Undo mutation and return to original program
      [undoSynchronizeStatementMutation]
end rule

%------------------------------------------------------------
%
%------------------------------------------------------------
function doSynchronizeStatementMutation

  replace * [statement]
    AStmt [statement]

  deconstruct AStmt
    OtherStatement [other_statement]

  % create mutant comment to appear in source
  construct MutantString [stringlit]
    "ASAT (Added Sync Around Statement)"

  import synchVar [id]

  by
    'MUTATED /* 'MUTANT: MutantString */
    'synchronized '( synchVar ')
    '{
      OtherStatement
    '}
    /* 'MUTANT: MutantString */
end function

%---------------------
% Match the variable name in the statement
%---------------------

rule ContainsID VarName [id]
  match * [id]
    VarName
end rule

%------------------------------------------------------------
% Reinsert the orginal statement declaration but leave the
% MUTATED attribute to indicate that the mutant has already
% been created.
%------------------------------------------------------------
function undoSynchronizeStatementMutation
  replace * [statement]
      AStmt [statement]

  deconstruct AStmt
      SyncStmt [sync_other_statement]

  deconstruct SyncStmt
    'MUTATED /* 'MUTANT: MutantStr1 [stringlit] */
    'synchronized '( synchVar [id] ')
    '{
      OthStmt [other_statement]
    '}
    /* 'MUTANT: MutantStr2 [stringlit] */

  by
    % replace mutated statement with original but
    % leave hidden attribute
    'MUTATED
      OthStmt
end function

%Include rules for writing mutants to files
include "WriteMutants.Txl"
