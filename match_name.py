#!/usr/bin/env python3

"""
按时间戳匹配图像和点云，并将匹配结果复制为四位数字序号。

文件名需要包含 “秒-纳秒” 格式的时间戳，例如：

    1672531651-960983038.pcd
    1790527029-137512519.png

当前相机和雷达使用了不同的绝对时间基准，
因此两者时间戳存在一个很大的固定偏移。

程序以雷达为基准：

    理论图片时间戳
        =
    雷达时间戳 + TIME_OFFSET_NS

然后在理论图片时间附近寻找时间差最小、
且尚未被使用的图片。

原文件不会被修改。
匹配成功后会复制到输出文件夹，并重新编号为：

    0001.png
    0001.pcd

    0002.png
    0002.pcd

默认 EXECUTE = False，只预览，不实际复制。
"""

import os
import re
import shutil

from bisect import bisect_left, bisect_right


# ============================================================
#                       配置区
# ============================================================


# -------------------- 输入文件夹 --------------------

SOURCE_IMAGE_FOLDER = r"/media/ori/CAE5-029B/928/image"

SOURCE_PCD_FOLDER = r"/media/ori/CAE5-029B/928/lidar_raw"


# -------------------- 输出文件夹 --------------------

OUTPUT_IMAGE_FOLDER = r"/media/ori/CAE5-029B/928/biaoding/image"

OUTPUT_PCD_FOLDER = r"/media/ori/CAE5-029B/928/biaoding/lidar"


# ============================================================
# 固定时间偏移
#
# 定义：
#
#     图片时间戳
#         ≈
#     雷达时间戳 + TIME_OFFSET_NS
#
#
# 根据你提供的第一对时间戳：
#
# 雷达：
#     1672531651-960983038
#
# 图片：
#     1790527029-137512519
#
# 计算：
#
#     1790527029.137512519
#   - 1672531651.960983038
#
#   = 117995377.176529481 秒
#
# 转换为纳秒：
#
#   = 117995377176529481 ns
#
# ============================================================

TIME_OFFSET_NS = 117995377176529481


# ============================================================
# 补偿固定时间偏移以后，
# 相机与雷达允许存在的最大剩余时间误差。
#
# 单位：毫秒
#
# 例如：
#
#     MAX_TIME_DIFF_MS = 10.0
#
# 表示：
#
#     理论图片时间 ± 10 ms
#
# 范围内寻找最近的一张图片。
#
# 你的相机约 30 Hz：
#
#     一帧 ≈ 33.3 ms
#
# 因此这里不建议设置成 50 ms 甚至更大，
# 否则一个雷达时间附近可能同时出现多张相机图片。
#
# 建议先使用 10 ms。
# ============================================================

MAX_TIME_DIFF_MS = 50.0


# ============================================================
# 是否真正复制文件
#
# False：
#     只打印匹配结果，不修改任何文件
#
# True：
#     正式复制文件并重新编号
#
# 建议：
#     第一次先保持 False
#     查看匹配误差是否正常
#
# ============================================================

EXECUTE = True


# ============================================================
#                       配置区结束
# ============================================================


IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg"
}

PCD_EXT = ".pcd"


# 时间戳文件名格式：
#
#     秒-纳秒
#
# 例如：
#
#     1672531651-960983038
#
TIMESTAMP_RE = re.compile(
    r"^(\d+)-(\d+)$"
)


def scan_folder(folder, exts):
    """
    扫描文件夹并解析时间戳。

    返回格式：

        (
            原始文件名,
            文件名主体,
            扩展名,
            完整纳秒时间戳
        )

    例如：

        (
            "1672531651-960983038.pcd",
            "1672531651-960983038",
            ".pcd",
            1672531651960983038
        )
    """

    if not os.path.isdir(folder):

        raise NotADirectoryError(
            f"文件夹不存在: {folder}"
        )


    files = []

    invalid = []


    for fname in os.listdir(folder):

        name, ext = os.path.splitext(fname)

        ext = ext.lower()


        # 跳过不需要的文件类型
        if ext not in exts:
            continue


        # 检查文件名是否符合 秒-纳秒 格式
        match = TIMESTAMP_RE.fullmatch(name)


        if not match:

            invalid.append(fname)

            continue


        seconds, nanoseconds = (
            int(value)
            for value in match.groups()
        )


        # 将：
        #
        #     秒 + 纳秒
        #
        # 转换成完整整数纳秒时间戳
        #
        timestamp_ns = (
            seconds * 1_000_000_000
            + nanoseconds
        )


        files.append(
            (
                fname,
                name,
                ext,
                timestamp_ns
            )
        )


    # 打印无法解析的文件
    if invalid:

        print(
            f"警告：跳过 "
            f"{len(invalid)} "
            f"个无法解析时间戳的文件。"
        )

        for fname in sorted(invalid):

            print(
                f"  {fname}"
            )


    return files


def find_pairs(
    image_files,
    pcd_files,
    max_time_diff_ns
):
    """
    以每一帧雷达为基准寻找对应图片。

    核心逻辑：

        target_image_time
            =
        pcd_time + TIME_OFFSET_NS

    然后在：

        target_image_time - max_time_diff_ns

    到：

        target_image_time + max_time_diff_ns

    范围内寻找尚未匹配的图片。

    如果有多个候选图片，
    选择时间距离最近的一张。

    每张图片最多只会被匹配一次。
    """


    # 按时间戳排序
    images = sorted(
        image_files,
        key=lambda item: (
            item[3],
            item[0]
        )
    )


    pcds = sorted(
        pcd_files,
        key=lambda item: (
            item[3],
            item[0]
        )
    )


    # 单独保存所有图片时间戳
    # 方便后面二分查找
    image_times = [
        item[3]
        for item in images
    ]


    # 已经使用过的图片索引
    used_images = set()


    # 最终匹配结果
    pairs = []


    # 没有匹配成功的雷达
    unmatched_pcds = []


    for pcd in pcds:


        # ====================================================
        # 计算这一帧雷达理论上对应的相机时间
        # ====================================================

        target_image_time = (
            pcd[3]
            + TIME_OFFSET_NS
        )


        # ====================================================
        # 在：
        #
        #   目标时间 - 最大允许误差
        #
        # 到：
        #
        #   目标时间 + 最大允许误差
        #
        # 中寻找候选图片
        # ====================================================

        left = bisect_left(
            image_times,
            target_image_time
            - max_time_diff_ns
        )


        right = bisect_right(
            image_times,
            target_image_time
            + max_time_diff_ns
        )


        # 排除已经被其他雷达使用过的图片
        candidates = [
            index
            for index in range(
                left,
                right
            )
            if index not in used_images
        ]


        # 没有任何候选图片
        if not candidates:

            unmatched_pcds.append(
                pcd
            )

            continue


        # ====================================================
        # 如果范围内有多张图片，
        # 选择距离理论目标时间最近的一张
        # ====================================================

        image_index = min(
            candidates,
            key=lambda index: (
                abs(
                    image_times[index]
                    - target_image_time
                ),
                index
            )
        )


        used_images.add(
            image_index
        )


        image = images[
            image_index
        ]


        # ====================================================
        # 保存几个时间差
        # ====================================================

        # 原始相机时间 - 雷达时间
        raw_difference_ns = (
            image[3]
            - pcd[3]
        )


        # 补偿固定偏移后的误差
        compensated_difference_ns = (
            image[3]
            - target_image_time
        )


        pairs.append(
            (
                image,
                pcd,
                raw_difference_ns,
                compensated_difference_ns
            )
        )


    # 找出没有被使用的图片
    unmatched_images = [
        image
        for index, image in enumerate(
            images
        )
        if index not in used_images
    ]


    return (
        pairs,
        unmatched_images,
        unmatched_pcds
    )


def copy_pairs(pairs):
    """
    打印匹配结果。

    EXECUTE = False：
        仅预览。

    EXECUTE = True：
        正式复制。

    复制后文件名格式：

        0001.png
        0001.pcd

        0002.png
        0002.pcd
    """


    operations = []

    pair_plans = []


    for index, pair in enumerate(
        pairs,
        start=1
    ):


        (
            image,
            pcd,
            raw_difference_ns,
            compensated_difference_ns
        ) = pair


        new_base = (
            f"{index:04d}"
        )


        # 原始差值转换成秒
        raw_difference_sec = (
            raw_difference_ns
            / 1_000_000_000
        )


        # 补偿后误差转换成毫秒
        compensated_difference_ms = (
            compensated_difference_ns
            / 1_000_000
        )


        pair_plans.append(
            (
                new_base,
                image[0],
                pcd[0],
                raw_difference_sec,
                compensated_difference_ms
            )
        )


        # --------------------
        # 图片复制计划
        # --------------------

        image_source = os.path.join(
            SOURCE_IMAGE_FOLDER,
            image[0]
        )


        image_target = os.path.join(
            OUTPUT_IMAGE_FOLDER,
            new_base + image[2]
        )


        operations.append(
            (
                image_source,
                image_target
            )
        )


        # --------------------
        # PCD复制计划
        # --------------------

        pcd_source = os.path.join(
            SOURCE_PCD_FOLDER,
            pcd[0]
        )


        pcd_target = os.path.join(
            OUTPUT_PCD_FOLDER,
            new_base + pcd[2]
        )


        operations.append(
            (
                pcd_source,
                pcd_target
            )
        )


    # ========================================================
    # 检查文件冲突
    # ========================================================

    targets = set()

    has_conflict = False


    for source, target in operations:


        if target in targets:

            print(
                f"警告：目标名重复: "
                f"{target}"
            )

            has_conflict = True


        if os.path.exists(target):

            print(
                f"警告：目标文件已存在: "
                f"{target}"
            )

            has_conflict = True


        if not os.path.isfile(source):

            print(
                f"警告：源文件不存在或"
                f"不是普通文件: "
                f"{source}"
            )

            has_conflict = True


        targets.add(target)


    if has_conflict:

        print(
            "\n检测到文件冲突或"
            "源文件异常，"
            "已取消本批复制。"
        )

        return


    # ========================================================
    # 打印匹配情况
    # ========================================================

    print(
        "\n"
        "=============================="
    )

    print(
        "匹配和复制计划"
    )

    print(
        "==============================\n"
    )


    for (
        new_base,
        image_name,
        pcd_name,
        raw_difference_sec,
        compensated_difference_ms
    ) in pair_plans:


        image_ext = os.path.splitext(
            image_name
        )[1].lower()


        pcd_ext = os.path.splitext(
            pcd_name
        )[1].lower()


        print(
            f"[{new_base}]"
        )


        print(
            f"  图片:"
        )

        print(
            f"    {image_name}"
        )


        print(
            f"  PCD:"
        )

        print(
            f"    {pcd_name}"
        )


        print(
            f"  原始时间差:"
        )

        print(
            f"    {raw_difference_sec:+.9f} s"
        )


        print(
            f"  补偿后误差:"
        )

        print(
            f"    "
            f"{compensated_difference_ms:+.6f} ms"
        )


        print(
            f"  输出:"
        )

        print(
            f"    "
            f"{new_base}{image_ext}"
        )

        print(
            f"    "
            f"{new_base}{pcd_ext}"
        )


        print()


    # ========================================================
    # 只预览
    # ========================================================

    if not EXECUTE:

        print(
            "以上为预览。"
        )

        print(
            "当前 EXECUTE = False，"
            "未复制任何文件。"
        )

        print(
            "确认匹配正确以后，"
            "将 EXECUTE 改为 True "
            "再运行一次即可。"
        )

        return


    # ========================================================
    # 创建输出目录
    # ========================================================

    os.makedirs(
        OUTPUT_IMAGE_FOLDER,
        exist_ok=True
    )


    os.makedirs(
        OUTPUT_PCD_FOLDER,
        exist_ok=True
    )


    temporary_operations = []

    created_targets = []


    try:


        # ====================================================
        # 第一步：
        # 先复制成临时文件
        # ====================================================

        for index, (
            source,
            target
        ) in enumerate(operations):


            temporary = (
                f"{target}"
                f".match_name_tmp_"
                f"{os.getpid()}_"
                f"{index}"
            )


            if os.path.exists(
                temporary
            ):

                raise FileExistsError(
                    f"临时文件已存在: "
                    f"{temporary}"
                )


            temporary_operations.append(
                (
                    temporary,
                    target
                )
            )


            shutil.copy2(
                source,
                temporary
            )


        # ====================================================
        # 第二步：
        # 所有临时文件复制完成以后，
        # 再改成最终名称
        # ====================================================

        for (
            temporary,
            target
        ) in temporary_operations:


            if os.path.exists(
                target
            ):

                raise FileExistsError(
                    f"目标文件在复制期间出现: "
                    f"{target}"
                )


            os.rename(
                temporary,
                target
            )


            created_targets.append(
                target
            )


    except Exception:


        # ====================================================
        # 如果出错，
        # 删除本次生成的临时文件和目标文件。
        #
        # 原始文件永远不会删除。
        # ====================================================

        for (
            temporary,
            _
        ) in temporary_operations:


            if os.path.exists(
                temporary
            ):

                try:

                    os.remove(
                        temporary
                    )

                except OSError:

                    pass


        for target in created_targets:


            if os.path.exists(
                target
            ):

                try:

                    os.remove(
                        target
                    )

                except OSError:

                    pass


        raise


    print(
        "\n复制和编号完成。"
    )

    print(
        f"共复制 "
        f"{len(pairs)} "
        f"对数据。"
    )

    print(
        "原始文件未修改。"
    )


def main():

    # ========================================================
    # 检查参数
    # ========================================================

    if MAX_TIME_DIFF_MS < 0:

        raise ValueError(
            "MAX_TIME_DIFF_MS "
            "不能小于 0。"
        )


    # ========================================================
    # 防止源文件夹和输出文件夹相同
    # ========================================================

    source_image_path = os.path.normcase(
        os.path.realpath(
            SOURCE_IMAGE_FOLDER
        )
    )


    source_pcd_path = os.path.normcase(
        os.path.realpath(
            SOURCE_PCD_FOLDER
        )
    )


    output_image_path = os.path.normcase(
        os.path.realpath(
            OUTPUT_IMAGE_FOLDER
        )
    )


    output_pcd_path = os.path.normcase(
        os.path.realpath(
            OUTPUT_PCD_FOLDER
        )
    )


    if (
        source_image_path
        ==
        output_image_path
    ):

        raise ValueError(
            "图片输出目录不能与"
            "图片源目录相同。"
        )


    if (
        source_pcd_path
        ==
        output_pcd_path
    ):

        raise ValueError(
            "PCD 输出目录不能与"
            "PCD 源目录相同。"
        )


    # ========================================================
    # 扫描文件
    # ========================================================

    print(
        "扫描文件夹..."
    )


    image_files = scan_folder(
        SOURCE_IMAGE_FOLDER,
        IMAGE_EXTS
    )


    pcd_files = scan_folder(
        SOURCE_PCD_FOLDER,
        {
            PCD_EXT
        }
    )


    print(
        f"图片文件: "
        f"{len(image_files)} 个"
    )


    print(
        f"PCD 文件: "
        f"{len(pcd_files)} 个"
    )


    if (
        not image_files
        or
        not pcd_files
    ):

        print(
            "错误：至少一个文件夹中"
            "没有找到可解析时间戳的文件。"
        )

        return


    # ========================================================
    # 毫秒转换成纳秒
    # ========================================================

    max_time_diff_ns = round(
        MAX_TIME_DIFF_MS
        * 1_000_000
    )


    # ========================================================
    # 打印当前配置
    # ========================================================

    print()

    print(
        "当前固定时间偏移："
    )

    print(
        f"  {TIME_OFFSET_NS} ns"
    )


    print(
        "换算成秒："
    )

    print(
        f"  "
        f"{TIME_OFFSET_NS / 1_000_000_000:.9f} s"
    )


    print(
        "最大允许补偿后误差："
    )

    print(
        f"  {MAX_TIME_DIFF_MS:g} ms"
    )


    # ========================================================
    # 匹配
    # ========================================================

    (
        pairs,
        unmatched_images,
        unmatched_pcds
    ) = find_pairs(
        image_files,
        pcd_files,
        max_time_diff_ns
    )


    # ========================================================
    # 匹配统计
    # ========================================================

    print()

    print(
        "=============================="
    )

    print(
        "匹配统计"
    )

    print(
        "=============================="
    )


    print(
        f"匹配成功: "
        f"{len(pairs)} 对"
    )


    print(
        f"未匹配图片: "
        f"{len(unmatched_images)} 个"
    )


    print(
        f"未匹配 PCD: "
        f"{len(unmatched_pcds)} 个"
    )


    # ========================================================
    # 显示未匹配的 PCD
    # ========================================================

    if unmatched_pcds:

        print()

        print(
            "未匹配的 PCD："
        )


        for pcd in unmatched_pcds:

            print(
                f"  {pcd[0]}"
            )


    # ========================================================
    # 执行复制或者预览
    # ========================================================

    if pairs:

        copy_pairs(
            pairs
        )

    else:

        print()

        print(
            "没有符合时间差阈值的"
            "文件对。"
        )


if __name__ == "__main__":

    main()