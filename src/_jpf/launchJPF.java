import gov.nasa.jpf.*;
import gov.nasa.jpf.listener.*;
import java.util.logging.Level;
import java.util.logging.Logger;

/* TODO
  - All info to run jpf is in config.py. See below for reasoning
  - Understand and implement logging

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

  public void runJPF() {
    try {
      jpfHasRun = false;

      /*  args contains a number of pieces of information
      +jpf.basedir = config._JPF_DIR
      +classpath = config._PROJECT_CLASS_DIR
      +sourcepath = config._PROJECT_SRC_DIR
      target = config._CHORD_MAIN
      target_args = config._CHORD_COMMAND_LINE
      cg.threads.break_arrays = config._JPF_SEARCH_ARRAYS
       */
      conf = JPF.createConfig(args);

      conf.setProperty("search.class", "gov.nasa.jpf.search.heuristic.Interleaving");
      conf.setProperty("search.multiple_errors", "false");
      //conf.setProperty("", "");

      jpf = new JPF(conf);

      // ----- Data-race listener
      jpfRaceDetector = new PreciseRaceDetector(conf);
      conf.setProperty("report.console.property_violation", "error");
      // Listener needs to be on both lists to work right
      jpf.addSearchListener(jpfRaceDetector);
      jpf.addVMListener(jpfRaceDetector);

      // ----- Deadlock analyzer
      jpfDeadlockAn = new DeadlockAnalyzer(conf, jpf);
      conf.setProperty("deadlock.format", "essential");
      jpf.addSearchListener(jpfDeadlockAn);
      jpf.addVMListener(jpfDeadlockAn);

      jpf.run();
      jpfHasRun = true;

      if (jpf.foundErrors()) {
        // ... process property violations discovered by JPF
        System.out.println("Race detector error message: "
          + jpfRaceDetector.getErrorMessage());
        // TODO: Deadlock error message
      }

    } catch (JPFConfigException cx) {
      // ... handle configuration exception
      // ...  can happen before running JPF and indicates inconsistent
      //      configuration data
    } catch (JPFException jx) {
      // ... handle exception while executing JPF,
      // ...  JPFListenerException - occurred from within configured listener
      // ...  JPFNativePeerException - occurred from within MJI method/native peer
      // ...  all others indicate JPF internal errors
    } // try-catch

    System.out.println("CORE invocation of JPF ended.");
  } // RunJPF

  public Boolean hasJPFRun() {
    return jpfHasRun;
  }

  public String getDataRaceErrorMessage() {
    if (!jpfHasRun)
      return "Error, JPF analysis hasn't been performed yet.";

    if (jpf.foundErrors())
      return jpfRaceDetector.getErrorMessage();
    else
      return null;
  }

  public String getDeadlockErrorMessage() {
    if (!jpfHasRun)
      return "Error, JPF analysis hasn't been performed yet.";

    //if (jpf.foundErrors())
    // TODO: I'm not sure how to get the deadlock error message.
    //       It isn't as simple as the data-race one
    return null;
  }

  public static void main(String[] args) {
    launchJPF gogoJPF;
    gogoJPF = new launchJPF(args);
    gogoJPF.runJPF();

  } // main
} // class