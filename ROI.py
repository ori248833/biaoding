import open3d as o3d
import numpy as np
import os
import glob
import time

def process_pcd_folder(input_folder, output_folder, min_radius=1.0,max_radius=5.0):
    """
    批量处理PCD文件，根据半径进行ROI裁剪。
    
    Args:
        input_folder (str): 输入PCD文件的文件夹路径
        output_folder (str): 输出保存路径
        roi_radius (float): ROI半径（米）
    """
    
    # 1. 确保输出目录存在
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"创建输出目录: {output_folder}")

    # 2. 获取所有pcd文件
    # 这里的 *.pcd 会匹配所有以 .pcd 结尾的文件
    pcd_files = glob.glob(os.path.join(input_folder, "*.pcd"))
    
    if not pcd_files:
        print(f"错误: 在 {input_folder} 中没有找到 .pcd 文件。")
        return

    print(f"找到 {len(pcd_files)} 个文件，准备开始处理...")
    #print(f"ROI 半径设置为: {roi_radius} 米")
    print("-" * 30)

    start_time = time.time()
    
    for i, file_path in enumerate(pcd_files):
        try:
            # --- 步骤 A: 读取点云 ---
            file_name = os.path.basename(file_path)
            print(f"正在处理 [{i+1}/{len(pcd_files)}]: {file_name}") # 如果文件太多，可以注释掉这行减少刷屏
            
            pcd = o3d.io.read_point_cloud(file_path)
            
            if pcd.is_empty():
                print(f"警告: 文件 {file_name} 是空的，跳过。")
                continue

            # --- 步骤 B: 计算距离并筛选 ---
            # 将点云转换为numpy数组以便计算
            points = np.asarray(pcd.points)
            
            # 计算每个点到原点(0,0,0)的欧几里得距离
            # axis=1 表示按行计算 (x^2 + y^2 + z^2)^0.5
            distances = np.linalg.norm(points, axis=1)
            
            # 找到距离小于等于 roi_radius 的点的索引
            ind = np.where((distances >= min_radius) & (distances <= max_radius))[0]
            
            # 使用索引从原始pcd中选择点 (这样可以保留强度 intensity 等其他通道信息)
            pcd_roi = pcd.select_by_index(ind)

            # --- 步骤 C: 保存结果 ---
            save_path = os.path.join(output_folder, file_name)
            
            # write_ascii=False 保存为二进制模式，文件更小读取更快
            # 如果你需要用文本编辑器查看内容，可以改为 True
            o3d.io.write_point_cloud(save_path, pcd_roi, write_ascii=False)
            
        except Exception as e:
            print(f"处理文件 {file_name} 时发生错误: {e}")

    end_time = time.time()
    duration = end_time - start_time
    
    print("-" * 30)
    print(f"处理完成！")
    print(f"共处理文件: {len(pcd_files)} 个")
    print(f"总耗时: {duration:.2f} 秒")
    print(f"输出文件保存在: {output_folder}")

if __name__ == "__main__":
    # ================= 配置区域 =================
    
    # 输入文件夹路径 (请修改这里)
    INPUT_DIR = "/media/ori/Extreme_SSD/biaozhu819/lidar_points_raw" 
    
    # 输出文件夹路径 (脚本会自动创建)
    OUTPUT_DIR = "/media/ori/Extreme_SSD/biaozhu819/lidar_points_ROI"
    
    # ROI 半径 (米)
    min_r = 2.0
    max_r = 8.0
    
    # ===========================================
    
    process_pcd_folder(INPUT_DIR, OUTPUT_DIR, min_r,max_r )
