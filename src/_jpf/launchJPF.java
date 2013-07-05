import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.*;

// jpf libraries are in lib/JPF/
import gov.nasa.jpf.*;
import gov.nasa.jpf.listener.*;

// py4j is a python package for connecting to Java programs
import py4j.*;

/* TODO
  - Understand and implement JPF (and py4j?) logging

*/

public class launchJPF {

  protected
    String[] args;
    static Logger log = JPF.getLogger("MyLog");
    JPF jpf;
    Config conf;
    PreciseRaceDetector jpfRaceDetector;
    DeadlockAnalyzer jpfDeadlockAn;
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
      log.error("launchJPF.java, runJPF: Set args before calling runJPF.");
      return;
    }
    jpfHasRun = false;

    try {
      log.info("Create JPF's config");
      conf = JPF.createConfig(args);

      //conf.setProperty("search.class", "gov.nasa.jpf.search.heuristic.Interleaving");
      //conf.setProperty("search.multiple_errors", "false");
      //conf.setProperty("", "");

      log.info("Create jpf");
      jpf = new JPF(conf);

      // ----- Data-race listener
      log.info("Data race listener");
      jpfRaceDetector = new PreciseRaceDetector(conf);
      conf.setProperty("report.console.property_violation", "error");
      // Listener needs to be on both lists to work right
      jpf.addSearchListener(jpfRaceDetector);
      jpf.addVMListener(jpfRaceDetector);

      // ----- Deadlock analyzer
      log.info("Deadlock analyzer listener");
      jpfDeadlockAn = new DeadlockAnalyzer(conf, jpf);
      conf.setProperty("deadlock.format", "essential");
      jpf.addSearchListener(jpfDeadlockAn);
      jpf.addVMListener(jpfDeadlockAn);

      log.info("jpf.run()");
      jpf.run();
      jpfHasRun = true;


      log.info("Check for errors");
      if (jpf.foundErrors()) {
        // Not used ATM
      }

    } catch (JPFConfigException cx) {
      log.severe(cx.toString());
      // ... handle configuration exception
      // ...  can happen before running JPF and indicates inconsistent
      //      configuration data
    } catch (JPFException jx) {
      log.severe(jx.toString());
      // ... handle exception while executing JPF,
      // ...  JPFListenerException - occurred from within configured listener
      // ...  JPFNativePeerException - occurred from within MJI method/native peer
      // ...  all others indicate JPF internal errors
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

    if (jpf.foundErrors())
      return jpfRaceDetector.getErrorMessage();
    else
      return null;
  }

  public String getDeadlockErrorMessage() {
    if (!jpfHasRun)
      return null;

    //if (!jpf.foundErrors())
    //  return null;

    int numErrors = jpf.getSearch().getErrors().size();
    //if (numErrors == 0)
    //  return null;

    String errString = "abc";
    for (int i = 0; i <= numErrors; i++) {
      errString = errString + jpf.getSearch().getErrors().get(i).getDescription();
      errString = errString + jpf.getSearch().getErrors().get(i).getDetails();
    }

    return errString;
  }

  public launchJPF getJPFInstance() {
    return this;
  }

  public int getErrorCount() {
    if (jpfHasRun)
      return jpf.getSearch().getErrors().size();
    else
      return 0;
  }

  public String getErrorDescription(int i) {
    if (jpfHasRun)
      return jpf.getSearch().getErrors().get(i).getDescription();
    else
      return null;
  }

  public String getErrorDetails(int i) {
    if (jpfHasRun)
      return jpf.getSearch().getErrors().get(i).getDetails();
    else
      return null;
  }

  public static void main(String[] args) {
    launchJPF gogoJPF = new launchJPF(args);

    // py4j part
    GatewayServer server = new GatewayServer(gogoJPF);
    server.start();
  } // main
} // class