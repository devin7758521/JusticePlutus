# -*- coding: utf-8 -*-
"""
周K选股结果推送模块
================================================================================

功能：
1. 将选股结果推送到企业微信
2. 操作建议改为打星机制（最高五星，最低无星）
3. 五星最多一到两个

================================================================================
"""

from typing import List, Dict, Any


def convert_to_star_rating(sentiment_score: float, all_scores: List[float]) -> int:
    """
    将情绪评分转换为星级评分
    
    评分规则：
    - 五星：情绪评分 >= 80，且是所有股票中最高的（最多1-2个）
    - 四星：情绪评分 >= 70
    - 三星：情绪评分 >= 60
    - 二星：情绪评分 >= 50
    - 一星：情绪评分 >= 40
    - 无星：情绪评分 < 40
    
    Args:
        sentiment_score: 情绪评分（0-100）
        all_scores: 所有股票的情绪评分列表
        
    Returns:
        星级评分（0-5）
    """
    # 找出最高分和次高分
    sorted_scores = sorted(all_scores, reverse=True)
    top1_score = sorted_scores[0] if len(sorted_scores) > 0 else 0
    top2_score = sorted_scores[1] if len(sorted_scores) > 1 else 0
    
    # 五星：最高分且 >= 80（最多1-2个）
    if sentiment_score >= 80 and sentiment_score >= top2_score:
        return 5
    
    # 四星：>= 70
    if sentiment_score >= 70:
        return 4
    
    # 三星：>= 60
    if sentiment_score >= 60:
        return 3
    
    # 二星：>= 50
    if sentiment_score >= 50:
        return 2
    
    # 一星：>= 40
    if sentiment_score >= 40:
        return 1
    
    # 无星：< 40
    return 0


def star_rating_to_string(stars: int) -> str:
    """
    将星级评分转换为字符串
    
    Args:
        stars: 星级评分（0-5）
        
    Returns:
        星级字符串（如 "★★★★★"）
    """
    if stars == 0:
        return "☆☆☆☆☆"
    return "★" * stars + "☆" * (5 - stars)


def format_weekly_selection_message(
    stocks: List[Dict[str, Any]],
    ai_results: List[Dict[str, Any]],
    plan_type: str = "A"
) -> str:
    """
    格式化周K选股结果消息
    
    Args:
        stocks: 股票列表
        ai_results: AI分析结果列表
        plan_type: 方案类型（"A" 或 "B"）
        
    Returns:
        格式化后的消息
    """
    # 合并股票信息和AI分析结果
    merged_data = []
    all_scores = []
    
    for stock in stocks:
        code = stock['code']
        name = stock.get('name', '')
        
        # 查找对应的AI分析结果
        ai_result = None
        for result in ai_results:
            if result['code'] == code:
                ai_result = result
                break
        
        if ai_result:
            sentiment_score = ai_result.get('sentiment_score', 50)
            all_scores.append(sentiment_score)
            merged_data.append({
                'code': code,
                'name': name,
                'sentiment_score': sentiment_score,
                'analysis_summary': ai_result.get('analysis_summary', ''),
                'buy_reason': ai_result.get('buy_reason', ''),
                'key_points': ai_result.get('key_points', ''),
                'risk_warning': ai_result.get('risk_warning', ''),
            })
    
    # 计算星级评分
    for item in merged_data:
        item['stars'] = convert_to_star_rating(item['sentiment_score'], all_scores)
    
    # 按星级排序
    merged_data.sort(key=lambda x: x['stars'], reverse=True)
    
    # 格式化消息
    lines = []
    lines.append(f"📊 周K选股结果（方案{plan_type}）")
    lines.append("=" * 40)
    lines.append("")
    
    if not merged_data:
        lines.append("暂无符合条件的股票")
    else:
        for item in merged_data:
            stars_str = star_rating_to_string(item['stars'])
            lines.append(f"{item['code']} {item['name']}")
            lines.append(f"评级：{stars_str}")
            
            # 只显示有星级的股票的AI分析理由
            if item['stars'] > 0:
                if item['analysis_summary']:
                    lines.append(f"分析：{item['analysis_summary'][:100]}")
                if item['buy_reason']:
                    lines.append(f"理由：{item['buy_reason'][:100]}")
                if item['key_points']:
                    lines.append(f"看点：{item['key_points'][:100]}")
                if item['risk_warning']:
                    lines.append(f"风险：{item['risk_warning'][:100]}")
            
            lines.append("")
    
    lines.append("=" * 40)
    lines.append(f"共 {len(merged_data)} 只股票")
    
    # 统计星级分布
    star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0, 0: 0}
    for item in merged_data:
        star_counts[item['stars']] += 1
    
    lines.append(f"五星：{star_counts[5]}只 | 四星：{star_counts[4]}只 | 三星：{star_counts[3]}只")
    
    return "\n".join(lines)


def push_weekly_selection_to_wechat(
    stocks: List[Dict[str, Any]],
    ai_results: List[Dict[str, Any]],
    plan_type: str = "A",
    verbose: bool = True
) -> str:
    """
    推送周K选股结果到企业微信
    
    Args:
        stocks: 股票列表
        ai_results: AI分析结果列表
        plan_type: 方案类型（"A" 或 "B"）
        verbose: 是否打印详细信息
        
    Returns:
        格式化后的消息
    """
    try:
        # 格式化消息
        message = format_weekly_selection_message(stocks, ai_results, plan_type)
        
        if verbose:
            print("\n" + "=" * 80)
            print("推送消息到企业微信")
            print("=" * 80)
            print(message)
            print("=" * 80)
            print("✓ 消息已格式化（实际推送需要配置企业微信）")
        
        return message
        
    except Exception as e:
        if verbose:
            print(f"✗ 格式化失败: {e}")
        return ""


if __name__ == "__main__":
    # 测试打星机制
    print("=" * 80)
    print("测试打星机制")
    print("=" * 80)
    
    # 测试数据
    test_scores = [85, 75, 65, 55, 45, 35]
    
    print("\n情绪评分 → 星级评分:")
    for score in test_scores:
        stars = convert_to_star_rating(score, test_scores)
        stars_str = star_rating_to_string(stars)
        print(f"  {score:3d}分 → {stars_str} ({stars}星)")
    
    # 测试消息格式化
    print("\n" + "=" * 80)
    print("测试消息格式化")
    print("=" * 80)
    
    test_stocks = [
        {'code': '000001', 'name': '平安银行'},
        {'code': '000002', 'name': '万科A'},
        {'code': '000333', 'name': '美的集团'},
    ]
    
    test_ai_results = [
        {
            'code': '000001',
            'sentiment_score': 85,
            'analysis_summary': '基本面稳健，技术面向好，成交量放大明显',
            'buy_reason': '突破关键阻力位，成交量配合良好',
            'key_points': '业绩增长,估值合理,技术突破',
            'risk_warning': '市场波动风险'
        },
        {
            'code': '000002',
            'sentiment_score': 75,
            'analysis_summary': '行业景气度回升，公司基本面改善',
            'buy_reason': '估值修复空间较大',
            'key_points': '行业复苏,估值低,政策利好',
            'risk_warning': '房地产政策风险'
        },
        {
            'code': '000333',
            'sentiment_score': 65,
            'analysis_summary': '业绩稳定，但增长放缓',
            'buy_reason': '分红稳定，适合长期持有',
            'key_points': '分红稳定,现金流好',
            'risk_warning': '增长乏力'
        },
    ]
    
    message = format_weekly_selection_message(test_stocks, test_ai_results, "A")
    print(message)
