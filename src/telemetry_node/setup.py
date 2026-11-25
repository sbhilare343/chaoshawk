from setuptools import find_packages, setup

package_name = 'telemetry_node'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'numpy', 'scipy', 'matplotlib', 'scikit-learn', 'joblib'],
    zip_safe=True,
    maintainer='user',
    maintainer_email='sbhilare343@gmail.com',
    description='PX4 telemetry recording and live path visualization',
    license='BSD-3-Clause',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'telemetry = telemetry_node.telemetry_node:main',
            'path-viewer = telemetry_node.path_viewer:main',
            'uav-experiment = telemetry_node.experiment_cli:main',
            'train-supervisor = telemetry_node.train_supervisor:main',
            'sitl-demo = telemetry_node.sitl_demo:main',
            'chaos-gui = telemetry_node.gui:main',
            'ros-supervisor = telemetry_node.ros_supervisor:main',
            'live-chaos-metric = telemetry_node.live_nodes:metric_main',
            'px4-chaos-supervisor = telemetry_node.live_nodes:supervisor_main',
        ],
    },
)
