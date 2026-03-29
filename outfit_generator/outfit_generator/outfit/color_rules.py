"""
Правила цветовой сочетаемости
"""
from typing import List, Dict
from loguru import logger

from config import COLOR_GROUPS


class ColorHarmonyEngine:
    """Движок проверки цветовой сочетаемости"""
    
    def __init__(self):
        self.color_groups = COLOR_GROUPS
    
    def get_color_group(self, color: str) -> str:
        """Определение группы цвета"""
        color = color.lower().strip()
        
        for group_name, colors in self.color_groups.items():
            if color in colors:
                return group_name
        
        return "neutral"  # По умолчанию нейтральный
    
    def are_colors_compatible(self, colors1: List[str], colors2: List[str]) -> bool:
        """Проверка сочетаемости двух наборов цветов"""
        if not colors1 or not colors2:
            return True  # Если цвета не указаны, считаем совместимыми
        
        for c1 in colors1:
            group1 = self.get_color_group(c1)
            
            for c2 in colors2:
                group2 = self.get_color_group(c2)
                
                # Нейтральные цвета сочетаются со всем
                if group1 == "neutral" or group2 == "neutral":
                    return True
                
                # Одинаковые группы сочетаются
                if group1 == group2:
                    return True
                
                # Теплые + Натуральные
                if (group1 == "warm" and group2 == "natural") or \
                   (group1 == "natural" and group2 == "warm"):
                    return True
                
                # Холодные + Нейтральные
                if (group1 == "cool" and group2 == "neutral") or \
                   (group1 == "neutral" and group2 == "cool"):
                    return True
        
        return False
    
    def get_complementary_colors(self, color: str) -> List[str]:
        """Получение рекомендуемых сочетаемых цветов"""
        group = self.get_color_group(color)
        
        complementary = []
        
        # Всегда добавляем нейтральные
        complementary.extend(self.color_groups.get('neutral', []))
        
        # Добавляем цвета из той же группы
        complementary.extend(self.color_groups.get(group, []))
        
        # Специфические комбинации
        if group == "warm":
            complementary.extend(self.color_groups.get('natural', []))
        elif group == "cool":
            complementary.extend(self.color_groups.get('neutral', []))
        
        return list(set(complementary))
    
    def score_color_harmony(self, colors: List[List[str]]) -> float:
        """
        Оценка гармонии набора цветов
        Возвращает score от 0 до 1
        """
        if len(colors) < 2:
            return 1.0
        
        compatible_pairs = 0
        total_pairs = 0
        
        for i in range(len(colors)):
            for j in range(i + 1, len(colors)):
                total_pairs += 1
                if self.are_colors_compatible(colors[i], colors[j]):
                    compatible_pairs += 1
        
        return compatible_pairs / total_pairs if total_pairs > 0 else 1.0
    
    def suggest_color_adjustments(
        self,
        outfit_colors: List[Dict[str, List[str]]]
    ) -> Dict[str, any]:
        """
        Предложения по улучшению цветовой гармонии
        """
        suggestions = []
        
        # Проверка доминирующего цвета
        all_colors = []
        for item in outfit_colors:
            all_colors.extend(item.get('colors', []))
        
        if all_colors:
            # Подсчет частоты цветов
            color_counts = {}
            for color in all_colors:
                color_counts[color.lower()] = color_counts.get(color.lower(), 0) + 1
            
            dominant_color = max(color_counts, key=color_counts.get)
            suggestions.append(f"Доминирующий цвет: {dominant_color}")
            
            # Рекомендации
            complementary = self.get_complementary_colors(dominant_color)
            suggestions.append(f"Рекомендуемые дополняющие цвета: {', '.join(complementary[:5])}")
        
        return {
            "harmony_score": self.score_color_harmony([item.get('colors', []) for item in outfit_colors]),
            "suggestions": suggestions
        }