import React, { useState } from 'react';
import { Calendar } from 'lucide-react';

export default function DayPicker({ selectedDays, onDaysChange }) {
  const days = [
    { id: 'mon', label: 'Mon', full: 'Monday' },
    { id: 'tue', label: 'Tue', full: 'Tuesday' },
    { id: 'wed', label: 'Wed', full: 'Wednesday' },
    { id: 'thu', label: 'Thu', full: 'Thursday' },
    { id: 'fri', label: 'Fri', full: 'Friday' },
    { id: 'sat', label: 'Sat', full: 'Saturday' },
    { id: 'sun', label: 'Sun', full: 'Sunday' }
  ];

  const toggleDay = (dayId) => {
    const newSelected = new Set(selectedDays);
    if (newSelected.has(dayId)) {
      newSelected.delete(dayId);
    } else {
      newSelected.add(dayId);
    }
    onDaysChange(newSelected);
  };

  const selectAll = () => {
    onDaysChange(new Set(days.map(d => d.id)));
  };

  const clearAll = () => {
    onDaysChange(new Set());
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full">
        <div className="flex items-center gap-3 mb-6">
          <Calendar className="w-8 h-8 text-indigo-600" />
          <h2 className="text-2xl font-bold text-gray-800">Select Days</h2>
        </div>

        <div className="grid grid-cols-7 gap-2 mb-6">
          {days.map(day => (
            <button
              key={day.id}
              onClick={() => toggleDay(day.id)}
              className={`
                aspect-square rounded-lg font-semibold text-sm transition-all duration-200
                ${selectedDays.has(day.id)
                  ? 'bg-indigo-600 text-white shadow-lg scale-105'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }
              `}
              title={day.full}
            >
              {day.label}
            </button>
          ))}
        </div>

        <div className="flex gap-2 mb-4">
          <button
            onClick={selectAll}
            className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
          >
            Select All
          </button>
          <button
            onClick={clearAll}
            className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors"
          >
            Clear All
          </button>
        </div>

        {selectedDays.size > 0 && (
          <div className="bg-indigo-50 rounded-lg p-4">
            <p className="text-sm font-medium text-indigo-900 mb-2">
              Selected ({selectedDays.size}):
            </p>
            <p className="text-indigo-700">
              {days
                .filter(day => selectedDays.has(day.id))
                .map(day => day.full)
                .join(', ')}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}