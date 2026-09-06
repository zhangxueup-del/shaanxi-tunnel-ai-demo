from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


SOURCE = Path('/workspace/scratch/9725e58b6506/upload/陕西省隧道地理实体数据集_空间赋位初版.xlsx')
OUTPUT = Path('/workspace/sites/shaanxi-tunnel-ai-demo/src/data/tunnels.json')

# 仅用于Demo地图展示的近似位置。原始表中有坐标的记录始终优先使用原始坐标；
# 其余位置不会回写数据源，并在界面中明确标注“线性参考/范围示意”。
DEMO_COORDINATES = {
    'SX-TUN-0001': [108.505, 33.805],
    'SX-TUN-0002': [108.491, 33.779],
    'SX-TUN-0003': [108.472568, 33.746143],
    'SX-TUN-0004': [108.441518, 33.704148],
    'SX-TUN-0005': [108.015, 35.018],
    'SX-TUN-0006': [109.710, 35.420],
    'SX-TUN-0007': [108.966667, 33.883333],
    'SX-TUN-0008': [109.185, 32.955],
    'SX-TUN-0009': [106.248, 32.790],
    'SX-TUN-0010': [110.092, 32.800],
    'SX-TUN-0011': [109.990, 32.840],
    'SX-TUN-0012': [109.735, 32.842],
    'SX-TUN-0013': [109.370, 32.835],
    'SX-TUN-0014': [109.125, 32.748],
    'SX-TUN-0015': [108.245, 33.040],
    'SX-TUN-0016': [109.965, 33.500],
    'SX-TUN-0017': [110.245, 33.285],
    'SX-TUN-0018': [109.125, 33.600],
    'SX-TUN-0019': [109.675, 33.505],
    'SX-TUN-0020': [106.155, 33.325],
    'SX-TUN-0021': [109.755513, 34.136857],
    'SX-TUN-0022': [108.535, 32.515],
    'SX-TUN-0023': [109.455, 32.165],
    'SX-TUN-0024': [109.525, 31.990],
    'SX-TUN-0025': [109.050, 32.560],
    'SX-TUN-0026': [108.995, 32.455],
    'SX-TUN-0027': [108.970, 32.510],
    'SX-TUN-0028': [108.925, 32.360],
    'SX-TUN-0029': [107.050, 34.120],
    'SX-TUN-0030': [107.450, 33.210],
    'SX-TUN-0031': [107.400, 33.180],
    'SX-TUN-0032': [107.350, 33.155],
    'SX-TUN-0033': [107.290, 33.130],
}

DEMO_HEALTH = ['normal', 'attention', 'normal', 'warning', 'attention', 'normal',
               'warning', 'urgent', 'normal', 'uninspected', 'attention', 'normal',
               'warning', 'attention', 'normal', 'warning', 'attention', 'uninspected',
               'normal', 'attention', 'warning', 'urgent', 'normal', 'attention',
               'warning', 'normal', 'attention', 'normal', 'warning', 'attention',
               'normal', 'uninspected', 'attention']


def clean(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def main():
    main_table = pd.read_excel(SOURCE, sheet_name='隧道实体主表', header=2)
    spatial = pd.read_excel(SOURCE, sheet_name='空间赋位', header=2)
    joined = main_table.merge(
        spatial[['实体ID', '路线/路段', '线性参考/桩号', '空间赋位等级', '定位方式',
                 '当前可赋空间位置', '代表点经度', '代表点纬度', '行政区定位', '定位精度说明']],
        on='实体ID', how='left'
    )

    rows = []
    for index, row in joined.iterrows():
        entity_id = row['实体ID']
        source_lon = clean(row['代表点经度'])
        source_lat = clean(row['代表点纬度'])
        longitude, latitude = (
            [source_lon, source_lat]
            if source_lon is not None and source_lat is not None
            else DEMO_COORDINATES[entity_id]
        )
        spatial_grade = clean(row['空间赋位等级']) or '待赋位'
        position_type = (
            'verified' if spatial_grade.startswith(('A0', 'A1'))
            else 'linear' if spatial_grade.startswith('A2')
            else 'range'
        )
        status = DEMO_HEALTH[index]
        defect_count = {'normal': 0, 'attention': 2, 'warning': 5, 'urgent': 8, 'uninspected': 0}[status]
        health_score = {'normal': 92, 'attention': 78, 'warning': 61, 'urgent': 43, 'uninspected': None}[status]
        lengths = [clean(row.get('左洞长度(m)')), clean(row.get('右洞长度(m)')), clean(row.get('官方/单洞长度(m)'))]
        rows.append({
            'id': entity_id,
            'name': clean(row['隧道名称']),
            'alias': clean(row.get('别名/方向')),
            'road': clean(row.get('所属道路')) or clean(row.get('路线/路段')) or '道路信息待补',
            'routeCode': clean(row.get('路线编号')) or (str(clean(row.get('路线/路段')) or '').split(' ')[0] or '待补'),
            'routeSection': clean(row.get('路线/路段')),
            'city': clean(row.get('所在地市')) or '待补',
            'county': clean(row.get('所在区县')) or '待补',
            'maintenance': clean(row.get('管养单位')) or '待补充',
            'lengthLeft': lengths[0],
            'lengthRight': lengths[1],
            'lengthOfficial': lengths[2],
            'level': clean(row.get('隧道等级')) or '待补',
            'opened': clean(row.get('建成年份/通车年份')),
            'station': clean(row.get('中心桩号')) or clean(row.get('线性参考/桩号')),
            'attributeStatus': clean(row.get('属性核验状态')),
            'spatialGrade': spatial_grade,
            'positionMethod': clean(row.get('定位方式')),
            'positionDescription': clean(row.get('当前可赋空间位置')),
            'administrativeLocation': clean(row.get('行政区定位')),
            'accuracyNote': clean(row.get('定位精度说明')),
            'longitude': longitude,
            'latitude': latitude,
            'sourceCoordinate': source_lon is not None and source_lat is not None,
            'positionType': position_type,
            'healthStatus': status,
            'healthScore': health_score,
            'defectCount': defect_count,
            'lastInspection': None if status == 'uninspected' else f'2026-0{3 + (index % 6)}-{10 + (index % 17):02d}',
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'wrote {len(rows)} tunnel records to {OUTPUT}')


if __name__ == '__main__':
    main()
