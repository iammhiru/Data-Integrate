#!/bin/bash
# spark-submit batch_kpi.py vao cum Spark (driver chay trong container nay).
exec /opt/spark/bin/spark-submit \
  --conf spark.cores.max=${BATCH_CORES:-2} \
  --conf spark.executor.memory=${BATCH_EXECUTOR_MEMORY:-1g} \
  --conf spark.driver.memory=${BATCH_DRIVER_MEMORY:-1g} \
  --conf spark.driver.host=$(hostname) \
  --conf spark.sql.shuffle.partitions=8 \
  --conf "spark.driver.extraJavaOptions=-Duser.timezone=UTC" \
  --conf "spark.executor.extraJavaOptions=-Duser.timezone=UTC" \
  /opt/spark-apps/batch_kpi.py "$@"
