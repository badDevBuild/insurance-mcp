"""生成完整的黄金测试集模板

生成50个测试用例的模板文件，覆盖基础、对比和专项查询。
"""
import json
from pathlib import Path
import uuid

def generate_full_test_set():
    base_cases = [
        # 基础查询 (20个)
        ("保险期间多久？", "Process"),
        ("犹豫期是多少天？", "Definition"),
        ("如何申请理赔？", "Process"),
        ("什么情况不赔？", "Exclusion"),
        ("受益人可以变更吗？", "Process"),
        ("保单贷款利息怎么算？", "Process"),
        ("身故保险金怎么赔？", "Liability"),
        ("满期生存金有多少？", "Liability"),
        ("宽限期是多久？", "Definition"),
        ("未成年人身故有限制吗？", "Liability"),
        ("什么是现金价值？", "Definition"),
        ("合同效力中止是什么？", "Definition"),
        ("如何办理复效？", "Process"),
        ("年龄误告怎么办？", "Process"),
        ("什么是意外伤害？", "Definition"),
        ("猝死赔不赔？", "Liability"),
        ("住院津贴有多少？", "Liability"),
        ("什么是等待期？", "Definition"),
        ("保费自动垫交是什么？", "Process"),
        ("合同解除有损失吗？", "Process"),
        
        # 对比查询 (15个)
        ("退保和减额交清的区别？", "Comparison"),
        ("意外身故和疾病身故赔付有何不同？", "Comparison"),
        ("身故保险金和全残保险金的区别？", "Comparison"),
        ("保单贷款和保费垫交的区别？", "Comparison"),
        ("犹豫期内退保和犹豫期后退保的区别？", "Comparison"),
        ("趸交和期交的区别？", "Comparison"),
        ("投保人和被保险人的区别？", "Comparison"),
        ("受益人和继承人的区别？", "Comparison"),
        ("轻症和重疾的赔付比例对比？", "Comparison"),
        ("住院医疗和意外医疗的区别？", "Comparison"),
        ("定点医院和非定点医院报销区别？", "Comparison"),
        ("社保内和社保外用药报销区别？", "Comparison"),
        ("主险和附加险的关系？", "Comparison"),
        ("自动续保和重新投保的区别？", "Comparison"),
        ("宽限期内和中止期内出险的区别？", "Comparison"),
        
        # 专项查询 (15个)
        ("酒驾出事赔吗？", "Exclusion"),
        ("吸毒导致身故赔吗？", "Exclusion"),
        ("自杀赔不赔？", "Exclusion"),
        ("无证驾驶赔吗？", "Exclusion"),
        ("战争导致身故赔吗？", "Exclusion"),
        ("核辐射导致身故赔吗？", "Exclusion"),
        ("艾滋病赔吗？", "Exclusion"),
        ("既往症赔吗？", "Exclusion"),
        ("高风险运动赔吗？", "Exclusion"),
        ("精神疾病赔吗？", "Exclusion"),
        ("整容手术导致身故赔吗？", "Exclusion"),
        ("怀孕分娩导致身故赔吗？", "Exclusion"),
        ("犯罪行为导致身故赔吗？", "Exclusion"),
        ("减额交清表在哪里？", "Table"),
        ("现金价值表怎么查？", "Table")
    ]
    
    test_cases = []
    for i, (question, type_hint) in enumerate(base_cases, 1):
        query_type = "basic"
        if type_hint == "Comparison":
            query_type = "comparison"
        elif type_hint == "Exclusion":
            query_type = "exclusion"
        elif type_hint == "Table":
            query_type = "table"
            
        case = {
            "id": f"test_{i:03d}_{query_type}",
            "question": question,
            "query_type": query_type,
            "expected_section_ids": [], # 待标注
            "expected_category": type_hint if type_hint not in ["Comparison", "Table"] else None,
            "company": "平安人寿",
            "tier": 2 if query_type == "comparison" else (3 if query_type == "exclusion" else 1),
            "top_k": 5,
            "success_criteria": "待人工定义",
            "notes": f"自动生成的问题 - {type_hint}",
            "needs_labeling": True
        }
        test_cases.append(case)
    
    # 合并已有的8个case（如果有的话）
    # 这里我们直接生成全量
    
    full_set = {
        "name": "Phase5_Golden_Test_Set_Full",
        "version": "1.0.0",
        "description": "第五阶段向量检索黄金测试集 - 完整版（50个问题，待标注）",
        "total_count": len(test_cases),
        "test_cases": test_cases
    }
    
    output_path = Path("tests/golden_dataset/phase5_test_set_full.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(full_set, f, ensure_ascii=False, indent=2)
    
    print(f"生成了 {len(test_cases)} 个测试用例到 {output_path}")

if __name__ == "__main__":
    generate_full_test_set()

