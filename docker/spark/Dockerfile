# Spark 3.5.5 (Scala 2.12, Java 17, Python 3) + connector jars cho Kafka, S3A (MinIO), PostgreSQL.
# Jar duoc dong goi san trong image -> spark-submit khong can --packages / internet.
FROM apache/spark:3.5.5-scala2.12-java17-python3-ubuntu

ARG MAVEN=https://repo1.maven.org/maven2
ARG SPARK_VERSION=3.5.5

# Kafka source/sink cho Structured Streaming
ADD --chmod=644 ${MAVEN}/org/apache/spark/spark-sql-kafka-0-10_2.12/${SPARK_VERSION}/spark-sql-kafka-0-10_2.12-${SPARK_VERSION}.jar /opt/spark/jars/
ADD --chmod=644 ${MAVEN}/org/apache/spark/spark-token-provider-kafka-0-10_2.12/${SPARK_VERSION}/spark-token-provider-kafka-0-10_2.12-${SPARK_VERSION}.jar /opt/spark/jars/
ADD --chmod=644 ${MAVEN}/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar /opt/spark/jars/
ADD --chmod=644 ${MAVEN}/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar /opt/spark/jars/

# S3A filesystem (phai khop Hadoop 3.3.4 dong goi trong Spark 3.5)
ADD --chmod=644 ${MAVEN}/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar /opt/spark/jars/
ADD --chmod=644 ${MAVEN}/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar /opt/spark/jars/

# PostgreSQL JDBC
ADD --chmod=644 ${MAVEN}/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar /opt/spark/jars/

USER root
RUN mkdir -p /opt/spark-apps /opt/spark/work /opt/spark-checkpoints \
 && chown -R spark:spark /opt/spark/work /opt/spark-checkpoints
USER spark
WORKDIR /opt/spark
