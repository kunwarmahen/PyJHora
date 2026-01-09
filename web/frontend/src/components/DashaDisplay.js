import React from "react";
import "../styles/DashaDisplay.css";

export const DashaDisplay = ({ dashaData }) => {
  if (!dashaData || dashaData.status !== "success") {
    return <div className="error-message">Unable to calculate Dasha</div>;
  }

  const { current_dasha, next_dasha, dasha_sequence, current_bhukthi } =
    dashaData;

  return (
    <div className="dasha-container">
      <div className="dasha-title">
        <h3>Vimsottari Dasha Analysis</h3>
      </div>

      {/* Current & Next Dasha */}
      <div className="dasha-cards">
        <div className="dasha-card current">
          <div className="card-header">
            <h4>Current Dasha</h4>
          </div>
          <div className="card-content">
            <div className="dasha-lord">{current_dasha?.lord}</div>
            <div className="dasha-duration">
              Duration: <strong>{current_dasha?.duration_years} years</strong>
            </div>
            <p className="dasha-desc">{current_dasha?.description}</p>
          </div>
        </div>

        <div className="dasha-card next">
          <div className="card-header">
            <h4>Next Dasha</h4>
          </div>
          <div className="card-content">
            <div className="dasha-lord">{next_dasha?.lord}</div>
            <div className="dasha-duration">
              Duration: <strong>{next_dasha?.duration_years} years</strong>
            </div>
            <p className="dasha-desc">{next_dasha?.description}</p>
          </div>
        </div>
      </div>

      {/* Dasha Sequence */}
      {dasha_sequence && dasha_sequence.length > 0 && (
        <div className="dasha-sequence-section">
          <h4>Dasha Sequence (120-Year Cycle)</h4>
          <div className="dasha-sequence">
            {dasha_sequence.map((dasha, index) => (
              <div key={index} className="dasha-sequence-item">
                <div className="sequence-number">{dasha.order}</div>
                <div className="sequence-lord">{dasha.lord}</div>
                <div className="sequence-duration">{dasha.duration_years}y</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Current Bhukthi (Sub-periods) */}
      {current_bhukthi && Array.isArray(current_bhukthi.periods) && (
        <div className="bhukthi-section">
          <h4>{current_bhukthi.description}</h4>
          <div className="bhukthi-grid">
            {current_bhukthi.periods.map((period, index) => (
              <div key={index} className="bhukthi-card">
                <div className="bhukthi-lord">{period.lord}</div>
                <div className="bhukthi-duration">
                  {period.duration_months} months
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {dashaData.note && (
        <div className="dasha-note">
          <p>💡 {dashaData.note}</p>
        </div>
      )}
    </div>
  );
};
