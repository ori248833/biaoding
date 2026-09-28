import cv2
import numpy as np
import os
# ==============================================
# 你的相机参数（已确认是标准OpenCV格式，直接使用）
# ==============================================
K = np.array([
    [485.944457,   0.000000,   637.717299],
    [  0.000000, 485.491821,   351.173930],
    [  0.000000,   0.000000,     1.000000]
], dtype=np.float32)
D = np.array([-0.014489, -0.024145, 0.000000, 0.000000, 0.000000], dtype=np.float32)
# ==============================================
def main():
    print("="*50)
    print("        OpenCV 图像去畸变工具")
    print("="*50)
    print("说明：请将需要处理的图片放在本程序同一文件夹下")
    print("输入图片文件名（带扩展名，如 test.jpg）")
    print("输出将自动保存为 原文件名_r.扩展名")
    print("="*50)
    
    # 交互式输入文件名
    while True:
        input_filename = input("\n请输入要处理的图片文件名：").strip()
        
        # 检查文件是否存在
        if not os.path.exists(input_filename):
            print(f"❌ 错误：文件 '{input_filename}' 不存在，请检查文件名是否正确")
            continue
        
        # 检查是否是图片文件
        ext = os.path.splitext(input_filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.bmp']:
            print(f"❌ 错误：不支持的文件格式 '{ext}'，请使用 jpg/jpeg/png/bmp 格式")
            continue
        
        break
    
    # 生成输出文件名
    name, ext = os.path.splitext(input_filename)
    output_filename = f"{name}_r{ext}"
    
    print(f"\n🔄 正在处理：{input_filename}")
    
    # 读取图片
    img = cv2.imread(input_filename)
    if img is None:
        print(f"❌ 错误：无法读取图片文件，可能文件已损坏")
        return
    
    # 执行去畸变
    img_undistorted = cv2.undistort(img, K, D)
    
    # 保存结果
    cv2.imwrite(output_filename, img_undistorted)
    
    print(f"✅ 处理完成！")
    print(f"📥 输入文件：{input_filename}")
    print(f"📤 输出文件：{output_filename}")
    print(f"\n按回车键退出程序...")
    input()
if __name__ == "__main__":
    main()