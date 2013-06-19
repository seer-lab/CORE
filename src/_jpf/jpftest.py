# py4j is a library for calling java methods from python
# http://py4j.sourceforge.net/
from py4j.java_gateway import JavaGateway




gateway = JavaGateway()
random = gateway.jvm.java.util.Random()   # create a java.util.Random instance
number1 = random.nextInt(10)              # call the Random.nextInt method
number2 = random.nextInt(10)
print(number1,number2)
addition_app = gateway.entry_point        # get the AdditionApplication instance
addition_app.addition(number1,number2)    # call the addition method
