rm *.class

javac -cp /Users/kelk/workspace/CORE/lib/JPF/build/jpf.jar *.java

java -Xmx1024m -cp .:/Users/kelk/workspace/CORE/lib/JPF/build/jpf.jar launchJPF