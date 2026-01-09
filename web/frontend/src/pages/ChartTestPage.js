import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Star } from 'lucide-react';
import '../styles/Dashboard.css';

export const ChartTestPage = () => {
  const navigate = useNavigate();

  // Sample chart data for testing
  const [chartData] = useState({
    lagna: { house: 4, sign_name: 'Cancer', degrees: 15.23 },
    planets: {
      Sun: { house: 4, sign_name: 'Cancer', degrees: 10.5 },
      Moon: { house: 10, sign_name: 'Capricorn', degrees: 23.45 },
      Mars: { house: 7, sign_name: 'Libra', degrees: 5.67 },
      Mercury: { house: 4, sign_name: 'Cancer', degrees: 18.23 },
      Jupiter: { house: 11, sign_name: 'Aquarius', degrees: 12.34 },
      Venus: { house: 5, sign_name: 'Leo', degrees: 28.90 },
      Saturn: { house: 12, sign_name: 'Pisces', degrees: 8.45 },
      Rahu: { house: 1, sign_name: 'Aries', degrees: 15.78 },
      Ketu: { house: 7, sign_name: 'Libra', degrees: 15.78 }
    }
  });

  // Zodiac sign names
  const rasiNames = [
    'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
  ];

  // Planet abbreviations
  const planetAbbr = {
    'Sun': 'Su',
    'Moon': 'Mo',
    'Mars': 'Ma',
    'Mercury': 'Me',
    'Jupiter': 'Ju',
    'Venus': 'Ve',
    'Saturn': 'Sa',
    'Rahu': 'Ra',
    'Ketu': 'Ke'
  };

  // Get planets in a specific house
  const getPlanetsInHouse = (houseNum) => {
    const items = [];

    // Add Lagna if in this house
    if (chartData.lagna && chartData.lagna.house === houseNum) {
      items.push({ name: 'As', type: 'lagna', degrees: chartData.lagna.degrees });
    }

    // Find planets in this house
    Object.entries(chartData.planets).forEach(([name, data]) => {
      if (data.house === houseNum) {
        items.push({
          name: planetAbbr[name] || name,
          type: 'planet',
          fullName: name,
          degrees: data.degrees
        });
      }
    });

    return items;
  };

  // SVG-based North Indian Chart
  const SVGNorthIndianChart = () => {
    const width = 600;
    const height = 600;
    const size = 480; // Chart size
    const offset = (width - size) / 2; // Center the chart

    // Square coordinates
    const squareX = offset;
    const squareY = offset;

    // Key points on the square
    const topLeft = { x: squareX, y: squareY };
    const topRight = { x: squareX + size, y: squareY };
    const bottomLeft = { x: squareX, y: squareY + size };
    const bottomRight = { x: squareX + size, y: squareY + size };
    const topMid = { x: squareX + size / 2, y: squareY };
    const rightMid = { x: squareX + size, y: squareY + size / 2 };
    const bottomMid = { x: squareX + size / 2, y: squareY + size };
    const leftMid = { x: squareX, y: squareY + size / 2 };
    const center = { x: squareX + size / 2, y: squareY + size / 2 };

    // Define 12 houses with their center points for text placement
    // North Indian style: House 1 at top, going counterclockwise
    // Calculate the centroid of each triangular/polygonal section

    // Helper function to calculate centroid of a polygon
    const getCentroid = (points) => {
      const n = points.length;
      let cx = 0, cy = 0;
      for (let i = 0; i < n; i++) {
        cx += points[i].x;
        cy += points[i].y;
      }
      return { x: cx / n, y: cy / n };
    };

    // Define each house by its vertices, then calculate centroid
    const housePolygons = [
      // House 1: Top center triangle (topLeft, topMid, center, topRight arc)
      getCentroid([topMid, { x: topLeft.x + size * 0.25, y: topLeft.y + size * 0.25 }, center, { x: topRight.x - size * 0.25, y: topRight.y + size * 0.25 }]),

      // House 2: Top-left triangle
      getCentroid([topLeft, topMid, { x: topLeft.x + size * 0.25, y: topLeft.y + size * 0.25 }]),

      // House 3: Left-top triangle
      getCentroid([topLeft, { x: topLeft.x + size * 0.25, y: topLeft.y + size * 0.25 }, leftMid]),

      // House 4: Left center triangle
      getCentroid([leftMid, { x: leftMid.x + size * 0.25, y: topLeft.y + size * 0.25 }, center, { x: leftMid.x + size * 0.25, y: bottomLeft.y - size * 0.25 }]),

      // House 5: Left-bottom triangle
      getCentroid([leftMid, { x: leftMid.x + size * 0.25, y: bottomLeft.y - size * 0.25 }, bottomLeft]),

      // House 6: Bottom-left triangle
      getCentroid([bottomLeft, { x: leftMid.x + size * 0.25, y: bottomLeft.y - size * 0.25 }, bottomMid]),

      // House 7: Bottom center triangle
      getCentroid([bottomMid, { x: bottomLeft.x + size * 0.25, y: bottomLeft.y - size * 0.25 }, center, { x: bottomRight.x - size * 0.25, y: bottomRight.y - size * 0.25 }]),

      // House 8: Bottom-right triangle
      getCentroid([bottomMid, { x: bottomRight.x - size * 0.25, y: bottomRight.y - size * 0.25 }, bottomRight]),

      // House 9: Right-bottom triangle
      getCentroid([bottomRight, { x: bottomRight.x - size * 0.25, y: bottomRight.y - size * 0.25 }, rightMid]),

      // House 10: Right center triangle
      getCentroid([rightMid, { x: rightMid.x - size * 0.25, y: bottomRight.y - size * 0.25 }, center, { x: rightMid.x - size * 0.25, y: topRight.y + size * 0.25 }]),

      // House 11: Right-top triangle
      getCentroid([rightMid, { x: rightMid.x - size * 0.25, y: topRight.y + size * 0.25 }, topRight]),

      // House 12: Top-right triangle
      getCentroid([topRight, { x: topRight.x - size * 0.25, y: topRight.y + size * 0.25 }, topMid])
    ];

    const houses = housePolygons.map((centroid, index) => ({
      num: index + 1,
      cx: centroid.x,
      cy: centroid.y
    }));

    return (
      <svg width={width} height={height} style={{ maxWidth: '100%', height: 'auto' }}>
        <defs>
          {/* Gradient for chart border */}
          <linearGradient id="chartGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style={{ stopColor: 'var(--saffron)', stopOpacity: 1 }} />
            <stop offset="100%" style={{ stopColor: 'var(--vermillion)', stopOpacity: 1 }} />
          </linearGradient>
        </defs>

        {/* Outer square border */}
        <rect
          x={squareX}
          y={squareY}
          width={size}
          height={size}
          fill="white"
          stroke="url(#chartGradient)"
          strokeWidth="3"
        />

        {/* Two diagonal lines (corner to corner) */}
        <line x1={topLeft.x} y1={topLeft.y} x2={bottomRight.x} y2={bottomRight.y} stroke="var(--cosmic-indigo)" strokeWidth="2" />
        <line x1={topRight.x} y1={topRight.y} x2={bottomLeft.x} y2={bottomLeft.y} stroke="var(--cosmic-indigo)" strokeWidth="2" />

        {/* Six lines connecting midpoints to opposite corners */}
        {/* Top-mid to Right-mid */}
        <line x1={topMid.x} y1={topMid.y} x2={rightMid.x} y2={rightMid.y} stroke="var(--cosmic-indigo)" strokeWidth="2" />
        {/* Right-mid to Bottom-mid */}
        <line x1={rightMid.x} y1={rightMid.y} x2={bottomMid.x} y2={bottomMid.y} stroke="var(--cosmic-indigo)" strokeWidth="2" />
        {/* Bottom-mid to Left-mid */}
        <line x1={bottomMid.x} y1={bottomMid.y} x2={leftMid.x} y2={leftMid.y} stroke="var(--cosmic-indigo)" strokeWidth="2" />
        {/* Left-mid to Top-mid */}
        <line x1={leftMid.x} y1={leftMid.y} x2={topMid.x} y2={topMid.y} stroke="var(--cosmic-indigo)" strokeWidth="2" />

        {/* Draw all houses with their content */}
        {houses.map((house) => {
          const planetsInHouse = getPlanetsInHouse(house.num);

          return (
            <g key={house.num}>
              {/* House number */}
              <text
                x={house.cx}
                y={house.cy - 25}
                textAnchor="middle"
                fill="var(--text-secondary)"
                fontSize="11"
                fontWeight="600"
              >
                {house.num}
              </text>

              {/* Sign name */}
              <text
                x={house.cx}
                y={house.cy - 10}
                textAnchor="middle"
                fill="var(--cosmic-indigo)"
                fontSize="10"
                fontWeight="500"
              >
                {rasiNames[house.num - 1]}
              </text>

              {/* Planets in this house */}
              {planetsInHouse.map((item, idx) => (
                <g key={idx}>
                  <text
                    x={house.cx}
                    y={house.cy + 10 + idx * 18}
                    textAnchor="middle"
                    fill={item.type === 'lagna' ? 'var(--saffron)' : 'var(--cosmic-indigo)'}
                    fontSize="13"
                    fontWeight="700"
                  >
                    {item.name}
                  </text>
                  {/* Degrees */}
                  <text
                    x={house.cx}
                    y={house.cy + 22 + idx * 18}
                    textAnchor="middle"
                    fill="var(--text-secondary)"
                    fontSize="8"
                  >
                    {item.degrees?.toFixed(1)}°
                  </text>
                </g>
              ))}
            </g>
          );
        })}

        {/* Center label */}
        <text
          x={center.x}
          y={center.y - 5}
          textAnchor="middle"
          fill="var(--cosmic-indigo)"
          fontSize="12"
          fontWeight="700"
        >
          Rasi Chart
        </text>
        <text
          x={center.x}
          y={center.y + 10}
          textAnchor="middle"
          fill="var(--text-secondary)"
          fontSize="10"
        >
          North Indian
        </text>
      </svg>
    );
  };

  return (
    <div className="dashboard-container mandala-bg">
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-brand">
          <button onClick={() => navigate('/dashboard')} style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-sm)',
            color: 'var(--saffron)',
            padding: 'var(--space-sm) var(--space-md)',
            borderRadius: 'var(--radius-md)',
            transition: 'all 0.3s ease'
          }}
          onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 153, 51, 0.1)'}
          onMouseOut={(e) => e.currentTarget.style.background = 'none'}>
            <ArrowLeft size={20} />
            <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Back</span>
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginLeft: 'var(--space-lg)' }}>
            <div style={{
              width: '48px',
              height: '48px',
              background: 'linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white'
            }}>
              <Star size={24} />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Chart Design Test</h1>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                SVG North Indian Chart Prototype
              </p>
            </div>
          </div>
        </div>
      </nav>

      {/* Content */}
      <div className="dashboard-content">
        <div style={{
          background: 'white',
          borderRadius: 'var(--radius-xl)',
          padding: 'var(--space-xl)',
          boxShadow: 'var(--shadow-lg)',
          borderTop: '4px solid var(--saffron)',
          animation: 'fadeIn 0.6s ease-out'
        }}>
          <h3 style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-sm)',
            marginBottom: 'var(--space-lg)',
            color: 'var(--cosmic-indigo)',
            fontSize: '1.5rem'
          }}>
            <Star size={24} style={{ color: 'var(--saffron)' }} />
            SVG-Based North Indian Chart
          </h3>

          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: 'var(--space-xl)'
          }}>
            <SVGNorthIndianChart />
          </div>

          <div style={{
            marginTop: 'var(--space-xl)',
            padding: 'var(--space-lg)',
            background: 'var(--sacred-white)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--sandalwood)'
          }}>
            <h4 style={{ color: 'var(--cosmic-indigo)', marginBottom: 'var(--space-md)' }}>
              Design Notes:
            </h4>
            <ul style={{ color: 'var(--text-secondary)', lineHeight: '1.8', fontSize: '0.875rem' }}>
              <li>SVG-based for precise control and scalability</li>
              <li>Diamond shape (traditional North Indian style)</li>
              <li>12 houses properly divided</li>
              <li>Gradient border (saffron to vermillion)</li>
              <li>Hover effects on houses</li>
              <li>Planet abbreviations with degrees</li>
              <li>Ascendant (As) highlighted in saffron</li>
              <li>Responsive and clean typography</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
