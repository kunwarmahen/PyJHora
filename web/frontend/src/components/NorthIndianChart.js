import React from "react";
import "../styles/NorthIndianChart.css";

export const NorthIndianChart = ({ chartData }) => {
  if (!chartData || !chartData.planets) {
    return <div>No chart data</div>;
  }

  const { planets, lagna } = chartData;

  // Planet abbreviations for cleaner display
  const planetAbbr = {
    "Sun": "Su",
    "Moon": "Mo",
    "Mars": "Ma",
    "Mercury": "Me",
    "Jupiter": "Ju",
    "Venus": "Ve",
    "Saturn": "Sa",
    "Rahu": "Ra",
    "Ketu": "Ke"
  };

  // Rasi/Sign names
  const rasiNames = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
  ];

  // Get planets and lagna for a specific rasi (1-12)
  const getItemsInRasi = (rasiNum) => {
    const items = [];

    // Add Lagna if in this rasi
    if (lagna && lagna.house === rasiNum) {
      items.push({ name: "As", type: "lagna" }); // As = Ascendant/Lagna
    }

    // Find planets in this rasi
    Object.entries(planets).forEach(([name, data]) => {
      if (data.house === rasiNum) {
        items.push({ name: planetAbbr[name] || name, type: "planet" });
      }
    });

    return items;
  };

  // Map rasi numbers to visual positions in North Indian chart
  // Rasi 1 (Aries) = position 1 (top center)
  // Rasi 2 (Taurus) = position 2 (top right)
  // etc. in clockwise order
  const rasiPositions = [
    { rasi: 1, position: "1", row: "top" },
    { rasi: 2, position: "2", row: "top" },
    { rasi: 3, position: "3", row: "middle" },
    { rasi: 4, position: "4", row: "bottom" },
    { rasi: 5, position: "5", row: "bottom" },
    { rasi: 6, position: "6", row: "bottom" },
    { rasi: 7, position: "7", row: "bottom" },
    { rasi: 8, position: "8", row: "bottom" },
    { rasi: 9, position: "9", row: "bottom" },
    { rasi: 10, position: "10", row: "bottom" },
    { rasi: 11, position: "11", row: "middle" },
    { rasi: 12, position: "12", row: "top" }
  ];

  const renderHouse = (rasiNum, position) => {
    const items = getItemsInRasi(rasiNum);

    return (
      <div className={`house house-${position}`} key={rasiNum}>
        <div className="house-number">{rasiNum}</div>
        <div className="house-sign">{rasiNames[rasiNum - 1]}</div>
        <div className="planets-in-house">
          {items.map((item, i) => (
            <span key={i} className={`planet ${item.type}`}>
              {item.name}
            </span>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="north-indian-chart-container">
      <div className="chart-title">
        <h3>North Indian Chart (Rasi)</h3>
      </div>

      <div className="north-indian-chart">
        {/* Top Row - Rasis 12, 1, 2 */}
        <div className="chart-row top-row">
          {renderHouse(12, "12")}
          {renderHouse(1, "1")}
          {renderHouse(2, "2")}
        </div>

        {/* Middle Row - Rasis 11, Center, 3 */}
        <div className="chart-row middle-row">
          {renderHouse(11, "11")}
          <div className="center-info">
            <div className="center-text">{chartData.place || "Rasi Chart"}</div>
            <div className="center-text-small">
              {chartData.dob}
            </div>
            <div className="center-text-small">
              {chartData.tob}
            </div>
            {lagna && (
              <div className="lagna-info">
                Lagna: {rasiNames[lagna.house - 1]}
              </div>
            )}
          </div>
          {renderHouse(3, "3")}
        </div>

        {/* Bottom Row - Rasis 10, 9, 8, 7, 6, 5, 4 */}
        <div className="chart-row bottom-row">
          {renderHouse(10, "10")}
          {renderHouse(9, "9")}
          {renderHouse(8, "8")}
          {renderHouse(7, "7")}
          {renderHouse(6, "6")}
          {renderHouse(5, "5")}
          {renderHouse(4, "4")}
        </div>
      </div>
    </div>
  );
};
