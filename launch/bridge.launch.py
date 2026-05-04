"""Launch bridge with ros2_control — controller_manager + bridge node + robot_state_publisher."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    scene_path = LaunchConfiguration("scene_path", default="scenes/minimal_scene.json")
    controller_yaml = LaunchConfiguration("controller_yaml", default="configs/ros2_control.yaml")
    use_sim_time = LaunchConfiguration("use_sim_time", default="false")

    return LaunchDescription([
        DeclareLaunchArgument("scene_path", description="Path to scene definition JSON/YAML"),
        DeclareLaunchArgument("controller_yaml", description="ros2_control controller config"),
        DeclareLaunchArgument("use_sim_time", description="Use sim time for deterministic replay"),

        Node(
            package="controller_manager",
            executable="ros2_control_node",
            parameters=[{"use_sim_time": use_sim_time}, controller_yaml],
            output="screen",
        ),

        Node(
            package="controller_manager",
            executable="spawner",
            arguments=["joint_state_broadcaster", "--controller-manager", "/controller_manager"],
            output="screen",
        ),

        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[{"use_sim_time": use_sim_time}],
            output="screen",
        ),

        Node(
            package="surg_rl",
            executable="bridge_node",
            name="surg_rl_bridge",
            parameters=[{"scene_path": scene_path, "use_sim_time": use_sim_time}],
            output="screen",
        ),
    ])
