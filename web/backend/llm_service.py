"""
Unified LLM service supporting Qwen (Ollama), Gemini, and ChatGPT
"""
import httpx
import os
from typing import Optional, Dict, Any
from enum import Enum

class LLMProvider(str, Enum):
    QWEN = "qwen"
    GEMINI = "gemini"
    CHATGPT = "chatgpt"

class LLMService:
    """Unified interface for multiple LLM providers"""

    def __init__(self):
        # API keys and endpoints from environment
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.qwen_url = os.getenv("QWEN_API_URL", "http://localhost:11434")  # Ollama default

    async def ask_question(self,
                          chart_data: Dict[str, Any],
                          question: str,
                          provider: LLMProvider = LLMProvider.QWEN) -> str:
        """
        Ask a question about the chart using the specified LLM provider

        Args:
            chart_data: Complete chart data including planets, lagna, etc.
            question: User's question about their chart
            provider: Which LLM to use (qwen, gemini, or chatgpt)

        Returns:
            AI-generated response
        """
        prompt = self._build_chart_analysis_prompt(chart_data, question)

        if provider == LLMProvider.QWEN:
            return await self._call_qwen(prompt)
        elif provider == LLMProvider.GEMINI:
            return await self._call_gemini(prompt)
        elif provider == LLMProvider.CHATGPT:
            return await self._call_chatgpt(prompt)
        else:
            return "Unsupported LLM provider"

    async def generate_prediction(self,
                                 chart_data: Dict[str, Any],
                                 prediction_type: str = "general",
                                 provider: LLMProvider = LLMProvider.QWEN) -> str:
        """
        Generate predictions based on chart data

        Args:
            chart_data: Complete chart data
            prediction_type: Type of prediction (general, health, career, relationships)
            provider: Which LLM to use

        Returns:
            AI-generated prediction
        """
        prompt = self._build_prediction_prompt(chart_data, prediction_type)

        if provider == LLMProvider.QWEN:
            return await self._call_qwen(prompt)
        elif provider == LLMProvider.GEMINI:
            return await self._call_gemini(prompt)
        elif provider == LLMProvider.CHATGPT:
            return await self._call_chatgpt(prompt)
        else:
            return "Unsupported LLM provider"

    async def analyze_compatibility(self,
                                   male_chart: Dict[str, Any],
                                   female_chart: Dict[str, Any],
                                   koota_score: int,
                                   provider: LLMProvider = LLMProvider.QWEN) -> str:
        """
        Generate compatibility analysis

        Args:
            male_chart: Male birth chart data
            female_chart: Female birth chart data
            koota_score: Ashta Koota compatibility score
            provider: Which LLM to use

        Returns:
            AI-generated compatibility analysis
        """
        prompt = self._build_compatibility_prompt(male_chart, female_chart, koota_score)

        if provider == LLMProvider.QWEN:
            return await self._call_qwen(prompt)
        elif provider == LLMProvider.GEMINI:
            return await self._call_gemini(prompt)
        elif provider == LLMProvider.CHATGPT:
            return await self._call_chatgpt(prompt)
        else:
            return "Unsupported LLM provider"

    async def _call_qwen(self, prompt: str, max_tokens: int = 2000) -> str:
        """
        Call Qwen via Ollama
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "model": "qwen2.5:14b",  # or whatever Qwen model is installed
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": max_tokens
                    }
                }

                response = await client.post(
                    f"{self.qwen_url}/api/generate",
                    json=payload
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "No response from Qwen")
                else:
                    return f"Error from Qwen: {response.status_code} - {response.text}"
        except httpx.ConnectError:
            return "Error: Cannot connect to Ollama. Please ensure Ollama is running (ollama serve) and Qwen model is installed (ollama pull qwen2.5)."
        except Exception as e:
            return f"Error calling Qwen: {str(e)}"

    async def _call_gemini(self, prompt: str, max_tokens: int = 2000) -> str:
        """
        Call Google Gemini API
        """
        if not self.gemini_api_key:
            return "Error: GEMINI_API_KEY environment variable not set. Please add it to your .env file."

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"

                payload = {
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": max_tokens
                    }
                }

                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    if "candidates" in result and len(result["candidates"]) > 0:
                        content = result["candidates"][0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            return parts[0].get("text", "No response from Gemini")
                    return "No valid response from Gemini"
                else:
                    return f"Error from Gemini: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error calling Gemini: {str(e)}"

    async def _call_chatgpt(self, prompt: str, max_tokens: int = 2000) -> str:
        """
        Call OpenAI ChatGPT API
        """
        if not self.openai_api_key:
            return "Error: OPENAI_API_KEY environment variable not set. Please add it to your .env file."

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = "https://api.openai.com/v1/chat/completions"

                headers = {
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": "gpt-4o-mini",  # Use gpt-4o or gpt-4o-mini for cost efficiency
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert Vedic astrologer with deep knowledge of planetary positions, yogas, doshas, and their effects on human life. Provide insightful, personalized, and accurate astrological guidance."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": max_tokens
                }

                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        return result["choices"][0]["message"]["content"]
                    return "No response from ChatGPT"
                else:
                    return f"Error from ChatGPT: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error calling ChatGPT: {str(e)}"

    def _build_chart_analysis_prompt(self, chart_data: Dict[str, Any], question: str) -> str:
        """Build prompt for answering questions about a chart"""

        from datetime import datetime

        # Get current date for Dasha period identification
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Extract key information
        lagna_info = chart_data.get("lagna", {})
        moon_info = chart_data.get("moon_sign", {})
        sun_info = chart_data.get("sun_sign", {})
        planets = chart_data.get("planetary_positions", {})
        birth_details = chart_data.get("birth_details", {})

        # Build comprehensive chart description
        chart_description = f"""TODAY'S DATE: {current_date}

Birth Details:
- Date of Birth: {birth_details.get('dob', 'Unknown')}
- Time of Birth: {birth_details.get('tob', 'Unknown')}
- Place of Birth: {birth_details.get('place', 'Unknown')}

Lagna (Ascendant):
- Sign: {lagna_info.get('sign_name', 'Unknown')} (House #{lagna_info.get('house', 'Unknown')})
- Nakshatra: {lagna_info.get('nakshatra', 'Unknown')} Pada {lagna_info.get('nakshatra_pada', 'Unknown')}
- Degrees: {lagna_info.get('degrees', 'Unknown')}°

Moon Sign (Chandra Rasi):
- Sign: {moon_info.get('sign_name', 'Unknown')} (Rasi #{moon_info.get('rasi', 'Unknown')})
- Nakshatra: {moon_info.get('nakshatra', 'Unknown')} Pada {moon_info.get('nakshatra_pada', 'Unknown')}

Sun Sign (Surya Rasi):
- Sign: {sun_info.get('sign_name', 'Unknown')} (Rasi #{sun_info.get('rasi', 'Unknown')})
- Nakshatra: {sun_info.get('nakshatra', 'Unknown')} Pada {sun_info.get('nakshatra_pada', 'Unknown')}

Planetary Positions (All 9 Grahas):"""

        # Add planetary positions with nakshatras
        for planet, data in planets.items():
            nakshatra_info = ""
            if data.get('nakshatra'):
                nakshatra_info = f", Nakshatra: {data.get('nakshatra', 'Unknown')} Pada {data.get('nakshatra_pada', 'Unknown')}"
            chart_description += f"\n- {planet}: {data.get('sign_name', 'Unknown')} sign (Rasi #{data.get('rasi', 'Unknown')}), {data.get('degrees', 0):.2f}°{nakshatra_info}"

        # Add Dasha information
        current_dasha = chart_data.get("current_dasha", {})
        next_dasha = chart_data.get("next_dasha", {})
        current_bhukthi = chart_data.get("current_bhukthi", {})

        if current_dasha:
            chart_description += f"\n\nCurrent Dasha (Vimsottari):"
            chart_description += f"\n- Maha Dasha: {current_dasha.get('lord', 'Unknown')} ({current_dasha.get('start_date', 'Unknown')} to {current_dasha.get('end_date', 'Unknown')})"
            chart_description += f"\n- Duration: {current_dasha.get('duration_years', 0)} years"

        if current_bhukthi and current_bhukthi.get('periods'):
            chart_description += f"\n\nAll Sub-periods (Antar Dasha / Bhukti) within {current_dasha.get('lord', 'Unknown')} Maha Dasha:"
            # Show ALL sub-periods so LLM can identify which one is current
            for period in current_bhukthi.get('periods', []):
                chart_description += f"\n- {period.get('lord', 'Unknown')}: {period.get('start_date', 'Unknown')} to {period.get('end_date', 'Unknown')} ({period.get('duration_months', 0)} months)"

        if next_dasha:
            chart_description += f"\n\nNext Dasha:"
            chart_description += f"\n- {next_dasha.get('lord', 'Unknown')} starting {next_dasha.get('start_date', 'Unknown')}"

        prompt = f"""You are an expert Vedic astrologer. Below is the COMPLETE BIRTH CHART DATA for this person, calculated using precise astronomical calculations from the PyJHora Vedic astrology software. This is REAL, VERIFIED CHART DATA - not hypothetical.

=== COMPLETE BIRTH CHART ===

{chart_description}

=== END OF CHART DATA ===

IMPORTANT INSTRUCTIONS:
1. TODAY'S DATE is {current_date} - Use this to determine which Dasha and sub-period is CURRENTLY active
2. The above planetary positions, signs, houses, nakshatras, and Dasha periods have been calculated accurately based on the person's exact birth time and location
3. When asked about "current dasha" or "current period", check which Dasha/sub-period TODAY'S DATE ({current_date}) falls within
4. Use the complete chart data directly to answer their question

User's Question: {question}

Please provide a detailed, personalized answer based on THIS SPECIFIC BIRTH CHART. You have all the necessary information above. Analyze:
1. TODAY'S DATE ({current_date}) to identify the current Dasha and sub-period
2. The specific planetary positions in their chart
3. Their lagna (ascendant) in {lagna_info.get('sign_name', 'Unknown')}
4. Their moon sign in {moon_info.get('sign_name', 'Unknown')} and nakshatra {moon_info.get('nakshatra', 'Unknown')}
5. How the planets in their chart relate to the question asked
6. Practical, actionable guidance based on their specific placements

Do NOT ask for more information - you have the complete chart and today's date. Give a confident, detailed answer based on the data provided above."""

        return prompt

    def _build_prediction_prompt(self, chart_data: Dict[str, Any], prediction_type: str) -> str:
        """Build prompt for general predictions"""

        lagna_info = chart_data.get("lagna", {})
        moon_info = chart_data.get("moon_sign", {})
        planets = chart_data.get("planetary_positions", {})

        type_specific = {
            "general": "overall life path, personality, and general predictions",
            "health": "health constitution, potential health issues, and wellness recommendations",
            "career": "career inclinations, professional success factors, and recommended fields",
            "relationships": "relationship patterns, marriage timing, and compatibility factors"
        }

        focus = type_specific.get(prediction_type, type_specific["general"])

        prompt = f"""You are an expert Vedic astrologer. Below is the COMPLETE, ACCURATELY CALCULATED birth chart data from PyJHora software. Use this exact data for your predictions.

=== BIRTH CHART DATA ===

Lagna (Ascendant): {lagna_info.get('sign_name', 'Unknown')} in {lagna_info.get('nakshatra', 'Unknown')} nakshatra
Moon Sign: {moon_info.get('sign_name', 'Unknown')} in {moon_info.get('nakshatra', 'Unknown')} nakshatra
Sun Sign: {sun_info.get('sign_name', 'Unknown')}

Planetary Positions:
{self._format_planets(planets)}

=== END OF CHART DATA ===

Based on THIS SPECIFIC BIRTH CHART above, provide detailed {prediction_type} predictions focusing on {focus}.

Your prediction should cover:
1. Key strengths and characteristics based on their specific planetary placements
2. Challenges and areas for growth indicated by their chart
3. Opportunities in the near future based on current transits
4. Practical remedies or recommendations specific to their placements
5. Auspicious timing considerations for this person

IMPORTANT: Use the actual planetary positions shown above. Do NOT ask for more information - you have the complete chart data. Be specific, insightful, personalized, and encouraging."""

        return prompt

    def _build_compatibility_prompt(self, male_chart: Dict[str, Any],
                                   female_chart: Dict[str, Any], koota_score: int) -> str:
        """Build prompt for compatibility analysis"""

        male_lagna = male_chart.get("lagna", {})
        male_moon = male_chart.get("moon_sign", {})
        male_sun = male_chart.get("sun_sign", {})
        female_lagna = female_chart.get("lagna", {})
        female_moon = female_chart.get("moon_sign", {})
        female_sun = female_chart.get("sun_sign", {})

        prompt = f"""You are an expert Vedic astrologer specializing in marriage compatibility. Below are the COMPLETE, ACCURATELY CALCULATED birth charts for both partners from PyJHora software.

=== MALE BIRTH CHART ===
Lagna (Ascendant): {male_lagna.get('sign_name', 'Unknown')} in {male_lagna.get('nakshatra', 'Unknown')} nakshatra
Moon Sign: {male_moon.get('sign_name', 'Unknown')} in {male_moon.get('nakshatra', 'Unknown')} nakshatra (Pada {male_moon.get('pada', 'Unknown')})
Sun Sign: {male_sun.get('sign_name', 'Unknown')}

=== FEMALE BIRTH CHART ===
Lagna (Ascendant): {female_lagna.get('sign_name', 'Unknown')} in {female_lagna.get('nakshatra', 'Unknown')} nakshatra
Moon Sign: {female_moon.get('sign_name', 'Unknown')} in {female_moon.get('nakshatra', 'Unknown')} nakshatra (Pada {female_moon.get('pada', 'Unknown')})
Sun Sign: {female_sun.get('sign_name', 'Unknown')}

=== COMPATIBILITY SCORE ===
Ashta Koota Score: {koota_score}/36 (Calculated using traditional Vedic methods)

Interpretation:
- 28-36: Excellent compatibility
- 24-27: Good compatibility
- 18-23: Average compatibility (workable with effort)
- Below 18: Challenging compatibility

Based on these SPECIFIC CHARTS and the {koota_score}/36 Ashta Koota score, provide a comprehensive compatibility analysis:

1. Overall compatibility assessment - interpret the {koota_score}/36 score in context
2. Strengths in the relationship based on their specific placements
3. Potential challenges indicated by their charts and how to overcome them
4. Mental and emotional compatibility (Moon signs and nakshatras)
5. Long-term relationship prospects
6. Practical recommendations for a harmonious marriage

IMPORTANT: Use the actual chart data provided above. Be balanced, specific to their placements, insightful, and constructive. Do not ask for more information."""

        return prompt

    def _format_planets(self, planets: Dict[str, Any]) -> str:
        """Format planetary positions for prompt"""
        result = []
        for planet, data in planets.items():
            result.append(f"- {planet}: {data.get('sign_name', 'Unknown')}")
        return "\n".join(result)

# Singleton instance
llm_service = LLMService()
