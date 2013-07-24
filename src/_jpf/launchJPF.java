import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.*;

// JPF libraries are in core/lib/JPF/
import gov.nasa.jpf.*;
import gov.nasa.jpf.listener.*;

// py4j is a python package for connecting to Java programs
// JAR is in core/lib/Java
import py4j.*;

public class launchJPF {

  protected
    String[] args;
    static Logger log = JPF.getLogger("MyLog");
    JPF myJPF;
    Config conf;
    PreciseRaceDetector jpfRaceDetector;
    DeadlockAnalyzer jpfDeadlockAn;
    BudgetChecker jpfBudgetChecker;
    Boolean jpfHasRun;

  public launchJPF(String[] inArgs) {
    args = inArgs;
    jpfHasRun = false;
  }

  public void setArgs(String[] inArgs) {
    args = inArgs;
  }

  public void runJPF() {
    if (args == null) {
      log.info("launchJPF.java, runJPF: Set args before calling runJPF.");
      return;
    }
    jpfHasRun = false;

    try {
      conf = JPF.createConfig(args);;

      myJPF = new JPF(conf);

      // ----- Data-race listener
      jpfRaceDetector = new PreciseRaceDetector(conf);
      conf.setProperty("report.console.property_violation", "error");
      // Listener needs to be on both lists to work right
      myJPF.addSearchListener(jpfRaceDetector);
      myJPF.addVMListener(jpfRaceDetector);

      // ----- Deadlock analyzer
      jpfDeadlockAn = new DeadlockAnalyzer(conf, myJPF);
      conf.setProperty("deadlock.format", "essential");
      myJPF.addSearchListener(jpfDeadlockAn);
      myJPF.addVMListener(jpfDeadlockAn);

      // ----- Budget Checker
      jpfBudgetChecker = new BudgetChecker(conf, myJPF);
      myJPF.addSearchListener(jpfBudgetChecker);
      myJPF.addVMListener(jpfBudgetChecker);

      myJPF.run();
      jpfHasRun = true;

      if (myJPF.foundErrors()) {
        log.severe("Errors were found during the JPF run:");
      }

    } catch (JPFConfigException cx) {
      log.severe(cx.toString());
    } catch (JPFException jx) {
      log.severe(jx.toString());
    } // try-catch

    log.info("CORE invocation of JPF ended.");
  } // RunJPF


  public void resetJPF() {
    jpfHasRun = false;
  }

  public Boolean hasJPFRun() {
    return jpfHasRun;
  }

  public String getDataRaceErrorMessage() {
    if (!jpfHasRun)
      return null;

    if (myJPF.foundErrors())
      return jpfRaceDetector.getErrorMessage();
    else
      return null;
  }

  public String getDeadlockErrorMessage() {
    if (!jpfHasRun)
      return null;

    if (!myJPF.foundErrors())
      return null;

    int numErrors = getErrorCount();
    if (numErrors == 0)
      return null;

    // Deadlock error isn't as easy to get as the data race error
    // Assemble it from the pieces and return it
    String errString = "";
    for (int i = 0; i < numErrors; i++) {
      errString += " ";
      errString += getErrorDescription(i);
      errString += " ";
      errString += getErrorDetails(i);
    }

    return errString;
  }

  // Required by py4j
  public launchJPF getJPFInstance() {
    return this;
  }

  public int getErrorCount() {
    if (jpfHasRun)
      // from Search.java. Errors is a List<Error> type
      return myJPF.getSearch().getErrors().size();
    else
      return 0;
  }

  public String getErrorDescription(int i) {
    if (jpfHasRun)
      // From src/.../jpf/Error.java
      return myJPF.getSearch().getErrors().get(i).getDescription();
    else
      return null;
  }

  public String getErrorDetails(int i) {
    if (jpfHasRun)
      return myJPF.getSearch().getErrors().get(i).getDetails();
    else
      return null;
  }

  public List<Long> getStatistics()
  {
    if (!jpfHasRun)
      return null;

    // From  src/.../jpf/report/Statistics.java
    gov.nasa.jpf.report.Statistics statJPF = myJPF.getReporter().getRegisteredStatistics();
    // py4j handles lists better than arrays?
    List<Long> stat = new ArrayList<Long>();

    // 0 = max search depth, 1 = # visited states, 2 = # end states,
    // 3 =instructions executed, 4 = max memory used
    stat.add(Long.valueOf(statJPF.maxDepth));   // int
    stat.add(statJPF.visitedStates);   // long
    stat.add(statJPF.endStates);       // long
    stat.add(statJPF.insns);           // long
    stat.add(statJPF.maxUsed);         // long

    return stat;
  }

  public boolean timeExceeded()
  {
    if (!jpfHasRun)
      return false;

    // From  src/.../jpf/listener/BudgetChecker.java
    // NB: Submitted a bug report for this class, JPF 7, ver 1077
    return jpfBudgetChecker.timeExceeded();
  }

  public boolean depthLimitReached()
  {
    if (!jpfHasRun)
      return false;

    // From  src/.../jpf/search/Search.java
    gov.nasa.jpf.search.Search jpfSearch = myJPF.getSearch();
    return jpfSearch.getDepth() >= jpfSearch.getDepthLimit();
  }


  public static void main(String[] args) {
    // py4j needs this
    launchJPF gogoJPF = new launchJPF(args);
    GatewayServer server = new GatewayServer(gogoJPF);
    //try {

      server.start();
    //} catch (Exception ex) {
    //  launchJPF = null;
    //  server = null;
    //}
  } // main
} // class