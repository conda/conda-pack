Usage with Apache Spark on YARN
===============================

``conda-pack`` can be used to distribute conda environments to be used with
`Apache Spark <http://spark.apache.org/>`_ jobs when `deploying on Apache YARN
<http://spark.apache.org/docs/latest/running-on-yarn.html>`_. By bundling your
environment for use with Spark, you can make use of all the libraries provided
by ``conda``, and ensure that they're consistently provided on every node. This
makes use of `YARN's
<https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/YARN.html>`_
resource localization by distributing environments as archives, which are then
automatically unarchived on every node. In this case either the ``tar.gz`` or
``zip`` formats must be used.


Python Example
--------------

Create an environment:

.. code-block:: bash

    $ conda create -y -n example python=3.5 numpy pandas scikit-learn


Activate the environment:

.. code-block:: bash

    $ conda activate example   # Older conda versions use `source activate` instead


Package the environment into a ``tar.gz`` archive:

.. code-block:: bash

    $ conda pack -o environment.tar.gz
    Collecting packages...
    Packing environment at '/Users/jcrist/anaconda/envs/example' to 'environment.tar.gz'
    [########################################] | 100% Completed | 23.2s


Write a PySpark script, for example:

.. code-block:: python

    # script.py
    from pyspark import SparkConf
    from pyspark import SparkContext

    conf = SparkConf()
    conf.setAppName('spark-yarn')
    sc = SparkContext(conf=conf)

    def some_function(x):
        # Packages are imported and available from your bundled environment.
        import sklearn
        import pandas
        import numpy as np

        # Use the libraries to do work
        return np.sin(x)**2 + 2

    rdd = (sc.parallelize(range(1000))
             .map(some_function)
             .take(10))

    print(rdd)


Submit the job to Spark using ``spark-submit``. In YARN cluster mode:

.. code-block:: bash

    $ PYSPARK_PYTHON=./environment/bin/python \
    spark-submit \
    --conf spark.yarn.appMasterEnv.PYSPARK_PYTHON=./environment/bin/python \
    --master yarn \
    --deploy-mode cluster \
    --archives environment.tar.gz#environment \
    script.py


Or in YARN client mode:

.. code-block:: bash

    $ PYSPARK_DRIVER_PYTHON=`which python` \
    PYSPARK_PYTHON=./environment/bin/python \
    spark-submit \
    --conf spark.yarn.appMasterEnv.PYSPARK_PYTHON=./environment/bin/python \
    --master yarn \
    --deploy-mode client \
    --archives environment.tar.gz#environment \
    script.py


You can also start a PySpark interactive session using the following:

.. code-block:: bash

    $ PYSPARK_DRIVER_PYTHON=`which python` \
    PYSPARK_PYTHON=./environment/bin/python \
    pyspark \
    --conf spark.yarn.appMasterEnv.PYSPARK_PYTHON=./environment/bin/python \
    --master yarn \
    --deploy-mode client \
    --archives environment.tar.gz#environment


R Example
---------

Conda also supports R environments. Here we'll demonstrate creating and
packaging an environment for use with `Sparklyr <http://spark.rstudio.com/>`__.
Note that similar techniques also work with `SparkR
<https://spark.apache.org/docs/latest/sparkr.html>`__.

First, create an environment:

.. code-block:: bash

    $ conda create -y -n example r-sparklyr


Activate the environment:

.. code-block:: bash

    $ conda activate example   # Older conda versions use `source activate` instead


Package the environment into a ``tar.gz`` archive. Note the addition of the
``-d ./environment`` flag. This tells ``conda-pack`` to rewrite the any
prefixes to the path ``./environment`` (the relative path to the environment
from the working directory on the YARN workers) before packaging. This is
required for R, as the R executables have absolute paths hardcoded in them
(whereas Python does not).

.. code-block:: bash

    $ conda pack -o environment.tar.gz -d ./environment
    Collecting packages...
    Packing environment at '/Users/jcrist/anaconda/envs/example' to 'environment.tar.gz'
    [########################################] | 100% Completed | 21.8s


Write an R script, for example:

.. code-block:: r

    library(sparklyr)

    # Create a spark configuration
    config <- spark_config()

    # Specify that the packaged environment should be distributed
    # and unpacked to the directory "environment"
    config$spark.yarn.dist.archives <- "environment.tar.gz#environment"

    # Specify the R command to use, as well as various R locations on the workers
    config$spark.r.command <- "./environment/bin/Rscript"
    config$sparklyr.apply.env.R_HOME <- "./environment/lib/R"
    config$sparklyr.apply.env.RHOME <- "./environment"
    config$sparklyr.apply.env.R_SHARE_DIR <- "./environment/lib/R/share"
    config$sparklyr.apply.env.R_INCLUDE_DIR <- "./environment/lib/R/include"

    # Create a spark context.
    # You can also specify `master = "yarn-cluster"` for cluster mode.
    sc <- spark_connect(master = "yarn-client", config = config)

    # Use a user defined function, which requires a working R environment on
    # every worker node. Since all R packages already exist on every node, we
    # pass in ``packages = FALSE`` to avoid redistributing them.
    sdf_copy_to(sc, iris) %>%
        spark_apply(function(e) broom::tidy(lm(Petal_Length ~ Petal_Width, e)),
                    packages = FALSE)


Run the script.

.. code-block:: bash

    $ Rscript script.R
    # Source:   table<sparklyr_tmp_12de794b4e2a> [?? x 5]
    # Database: spark_connection
      Sepal_Length Sepal_Width Petal_Length Petal_Width  Species
      <chr>              <dbl>        <dbl>       <dbl>    <dbl>
    1 (Intercept)         1.08       0.0730        14.8 4.04e-31
    2 Petal_Width         2.23       0.0514        43.4 4.68e-86
