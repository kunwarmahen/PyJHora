"""
Integration with local Qwen LLM for generating AI-powered predictions
"""
import httpx
from typing import Optional
from config import settings

class QwenPredictor:
    """Interface to local Qwen LLM for astrological predictions"""
    
    @staticmethod
    async def generate_horoscope_prediction(chart_data: dict, user_query: Optional[str] = None) -> str:
        """
        Generate detailed horoscope prediction using Qwen
        
        Args:
            chart_data: Dictionary containing birth chart information
            user_query: Optional specific question from user
        
        Returns:
            Generated prediction text
        """
        if not settings.USE_QWEN:
            return "Qwen integration disabled"
        
        try:
            prompt = QwenPredictor._build_horoscope_prompt(chart_data, user_query)
            response = await QwenPredictor._call_qwen(prompt)
            return response
        except Exception as e:
            return f"Error generating prediction: {str(e)}"
    
    @staticmethod
    async def generate_compatibility_prediction(chart1: dict, chart2: dict, 
                                               compatibility_score: float) -> str:
        """
        Generate detailed relationship compatibility prediction using Qwen
        """
        if not settings.USE_QWEN:
            return "Qwen integration disabled"
        
        try:
            prompt = QwenPredictor._build_compatibility_prompt(chart1, chart2, compatibility_score)
            response = await QwenPredictor._call_qwen(prompt)
            return response
        except Exception as e:
            return f"Error generating prediction: {str(e)}"
    
    @staticmethod
    async def generate_health_prediction(chart_data: dict) -> str:
        """
        Generate health-focused prediction using Qwen
        """
        if not settings.USE_QWEN:
            return "Qwen integration disabled"
        
        try:
            prompt = QwenPredictor._build_health_prompt(chart_data)
            response = await QwenPredictor._call_qwen(prompt)
            return response
        except Exception as e:
            return f"Error generating prediction: {str(e)}"
    
    @staticmethod
    async def generate_career_prediction(chart_data: dict) -> str:
        """
        Generate career-focused prediction using Qwen
        """
        if not settings.USE_QWEN:
            return "Qwen integration disabled"
        
        try:
            prompt = QwenPredictor._build_career_prompt(chart_data)
            response = await QwenPredictor._call_qwen(prompt)
            return response
        except Exception as e:
            return f"Error generating prediction: {str(e)}"
    
    @staticmethod
    async def _call_qwen(prompt: str, max_tokens: int = 1000) -> str:
        """
        Internal method to call the Qwen API
        
        Expects local Qwen server running at settings.QWEN_API_URL
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": 0.7
                }
                
                response = await client.post(
                    f"{settings.QWEN_API_URL}/v1/completions",
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("choices", [{}])[0].get("text", "")
                else:
                    return f"Error from Qwen: {response.status_code}"
        except Exception as e:
            return f"Connection error: {str(e)}"
    
    @staticmethod
    def _build_horoscope_prompt(chart_data: dict, user_query: Optional[str] = None) -> str:
        """Build prompt for horoscope prediction"""
        prompt = f"""Based on the following astrological chart data, provide a detailed and personalized horoscope:

Birth Details:
- Date of Birth: {chart_data.get('dob', 'Unknown')}
- Time of Birth: {chart_data.get('tob', 'Unknown')}
- Place of Birth: {chart_data.get('place', 'Unknown')}

Chart Information:
- Lagna: {chart_data.get('lagna', 'Unknown')}
- Moon Sign: {chart_data.get('moon_sign', 'Unknown')}
- Sun Sign: {chart_data.get('sun_sign', 'Unknown')}

{f'User Question: {user_query}' if user_query else ''}

Please provide:
1. General personality traits based on the chart
2. Current life phase and challenges
3. Opportunities in the coming months
4. Areas to focus on for personal growth
5. Auspicious timings for important decisions"""
        
        return prompt
    
    @staticmethod
    def _build_compatibility_prompt(chart1: dict, chart2: dict, score: float) -> str:
        """Build prompt for compatibility prediction"""
        prompt = f"""Based on the following astrological charts of two individuals, provide a detailed compatibility analysis:

Person 1:
- Birth Date: {chart1.get('dob', 'Unknown')}
- Lagna: {chart1.get('lagna', 'Unknown')}
- Moon Sign: {chart1.get('moon_sign', 'Unknown')}

Person 2:
- Birth Date: {chart2.get('dob', 'Unknown')}
- Lagna: {chart2.get('lagna', 'Unknown')}
- Moon Sign: {chart2.get('moon_sign', 'Unknown')}

Compatibility Score: {score}/36

Please analyze:
1. Overall compatibility for marriage
2. Strengths in the relationship
3. Potential challenges to work through
4. Recommended timing for marriage
5. Advice for long-term harmony"""
        
        return prompt
    
    @staticmethod
    def _build_health_prompt(chart_data: dict) -> str:
        """Build prompt for health prediction"""
        prompt = f"""Based on the following astrological birth chart, provide health insights:

Birth Details:
- Date: {chart_data.get('dob', 'Unknown')}
- Lagna: {chart_data.get('lagna', 'Unknown')}

Chart Analysis: {chart_data.get('planets', {})}

Please provide:
1. Constitutional strengths and vulnerabilities
2. Potential health concerns based on planetary positions
3. Preventive health measures
4. Beneficial remedies and lifestyle suggestions
5. Auspicious timing for health treatments"""
        
        return prompt
    
    @staticmethod
    def _build_career_prompt(chart_data: dict) -> str:
        """Build prompt for career prediction"""
        prompt = f"""Based on the following astrological birth chart, provide career guidance:

Birth Details:
- Date: {chart_data.get('dob', 'Unknown')}
- Lagna: {chart_data.get('lagna', 'Unknown')}
- 10th House Lord: {chart_data.get('tenth_house_lord', 'Unknown')}

Please provide:
1. Natural career inclinations and strengths
2. Ideal career fields based on chart
3. Current career phase and opportunities
4. Obstacles and how to overcome them
5. Timing for career advancement or changes"""
        
        return prompt
