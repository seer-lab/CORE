rm *.class

javac -cp .:/Users/kelk/workspace/CORE/lib/JPF/build/jpf.jar:/Users/kelk/workspace/CORE/lib/Java/py4j0.8.jar *.java

java -Xmx1024m -cp .:/Users/kelk/workspace/CORE/lib/JPF/build/jpf.jar:/Users/kelk/workspace/CORE/lib/Java/py4j0.8.jar launchJPF