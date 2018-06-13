Usage with Apache Spark on YARN
===============================

``conda-pack`` can be used to distribute conda environments to be used with
`Apache Spark <http://spark.apache.org/>`_ jobs when `deploying on Apache YARN
<http://spark.apache.org/docs/latest/running-on-yarn.html>`_. By bundling your
environment for use with PySpark, you can make use of all the libraries
provided by ``conda``, and ensure that their consistently provided on every
node. This makes use of `YARN's
<https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/YARN.html>`_
resource localization by distributing environments as archives, which are then
automatically unarchived on every node. In this case either the ``tar.gz`` or
``zip`` formats must be used.


Example
-------

Create an environment:

.. code-block:: bash

    $ conda create -y -n example python=3.5 numpy pandas scikit-learn


Activate the environment:

.. code-block:: bash

    $ conda activate example   # Older conda versions use `source activate` instead


Package the environment into a ``zip`` archive:

.. code-block:: bash

    $ conda pack -o environment.zip
    Collecting packages...
    Packing environment at '/Users/jcrist/anaconda/envs/example' to 'environment.zip'
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
    --archives environment.zip#environment \
    script.py


Or in YARN client mode:

.. code-block:: bash

    $ PYSPARK_DRIVER_PYTHON=`which python` \
    PYSPARK_PYTHON=./environment/bin/python \
    spark-submit \
    --conf spark.yarn.appMasterEnv.PYSPARK_PYTHON=./environment/bin/python \
    --master yarn \
    --deploy-mode client \
    --archives environment.zip#environment \
    script.py
