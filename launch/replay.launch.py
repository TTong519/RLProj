"""Launch trajectory replay with ros2_control — controller_manager + replay node."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    model_path = LaunchConfiguration("model_path")
    control_freq = LaunchConfiguration("control_freq", default="100.0")
    use_sim_time = LaunchConfiguration("use_sim_time", default="false")

    return LaunchDescription([
        DeclareLaunchArgument("model_path", description="Path to SB3/RLlib checkpoint zip"),
        DeclareLaunchArgument("control_freq", description="Control frequency in Hz for replay"),
        DeclareLaunchArgument("use_sim_time", description="Use sim time"),

        Node(
            package="controller_manager",
            executable="ros2_control_node",
            parameters=[{"use_sim_time": use_sim_time}],
            output="screen",
        ),

        Node(
            package="surg_rl",
            executable="replay_node",
            name="surg_rl_replay",
            parameters=[{
                "model_path": model_path,
                "control_freq": control_freq,
                "use_sim_time": use_sim_time,
            }],
            output="screen",
        ),
    ])
