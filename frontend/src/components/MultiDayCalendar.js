import React, { useState } from 'react';
import { Calendar, ChevronLeft, ChevronRight, X } from 'lucide-react';
import Badge from '@mui/material/Badge';
import { styled } from '@mui/material/styles';

const StyledBadge = styled(Badge)(({ theme }) => ({
  '& .MuiBadge-badge': {
    right: -2,
    top: 2,
    border: `1px solid #fff`, // Thinner border
    padding: '0 2px',
    backgroundColor: '#3b82f6',
    color: 'white',
    fontSize: '0.55rem', // Smaller font
    height: '14px',       // Smaller height
    minWidth: '14px',     // Smaller width
    zIndex: 10,
  },
}));

export default function MultiDayCalendar({ selectedDates, onDatesChange, events = [] }) {
  const [currentDate, setCurrentDate] = useState(new Date());

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const getDaysInMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    return new Date(year, month + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    return new Date(year, month, 1).getDay();
  };

  const isSameDay = (d1, d2) => {
    return d1.getFullYear() === d2.getFullYear() &&
           d1.getMonth() === d2.getMonth() &&
           d1.getDate() === d2.getDate();
  };

  const isSelected = (day) => {
    const checkDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), day);
    return selectedDates.some(d => 
      d.getFullYear() === checkDate.getFullYear() &&
      d.getMonth() === checkDate.getMonth() &&
      d.getDate() === checkDate.getDate()
    );
  };

  const toggleDate = (day) => {
    const clickedDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), day);
    
    if (isSelected(day)) {
      onDatesChange(selectedDates.filter(d => !isSameDay(d, clickedDate)));
    } else {
      onDatesChange([...selectedDates, clickedDate]);
    }
  };

  const removeDate = (dateToRemove) => {
    onDatesChange(selectedDates.filter(d => !isSameDay(d, dateToRemove)));
  };

  const clearAll = () => {
    onDatesChange([]);
  };

  const previousMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1));
  };

  const formatDate = (date) => {
    return `${monthNames[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
  };

  const getEventCount = (date) => {
    return events.filter(item => {
      const event = item.event || item;
      if (!event.start_at) return false;
      const eventDate = new Date(event.start_at);
      return eventDate.getFullYear() === date.getFullYear() &&
             eventDate.getMonth() === date.getMonth() &&
             eventDate.getDate() === date.getDate();
    }).length;
  };

  const renderCalendar = () => {
    const daysInMonth = getDaysInMonth(currentDate);
    const firstDay = getFirstDayOfMonth(currentDate);
    const days = [];
    
    // Day headers
    const dayHeaders = dayNames.map(day => (
      <div key={day} className="h-6 flex items-center justify-center text-xs font-semibold text-gray-500 uppercase tracking-wider">
        {day}
      </div>
    ));

    // Empty cells
    for (let i = 0; i < firstDay; i++) {
      days.push(<div key={`empty-${i}`} className="h-8"></div>);
    }

    // Date cells
    for (let day = 1; day <= daysInMonth; day++) {
      const dayDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), day);
      const isSelectedDay = isSelected(day);
      const eventCount = getEventCount(dayDate);
      
      days.push(
        <button
          key={day}
          onClick={() => toggleDate(day)}
          className={`h-8 w-full flex items-center justify-center rounded-md text-sm font-medium transition-all hover:bg-blue-50 
            ${isSelectedDay ? 'bg-blue-500 text-white hover:bg-blue-600' : 'text-gray-700'}`}
        >
          <StyledBadge badgeContent={eventCount} invisible={eventCount === 0}>
            {day}
          </StyledBadge>
        </button>
      );
    }

    return (
      <div className="grid grid-cols-7 gap-1">
        {dayHeaders}
        {days}
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-blue-500" />
            <h2 className="text-lg font-bold text-gray-800">
              {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
            </h2>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentDate(new Date())}
              className="px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-md transition-colors border border-gray-200 mr-2"
            >
              Today
            </button>
            <button
              onClick={previousMonth}
              className="p-1.5 text-gray-600 hover:bg-gray-100 rounded-md transition-colors border border-gray-200"
              aria-label="Previous month"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={nextMonth}
              className="p-1.5 text-gray-600 hover:bg-gray-100 rounded-md transition-colors border border-gray-200"
              aria-label="Next month"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {renderCalendar()}
      </div>


      {selectedDates.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-800">
              Selected Dates ({selectedDates.length})
            </h3>
            <button
              onClick={clearAll}
              className="px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded-md transition-colors"
            >
              Clear All
            </button>
          </div>

          <div className="flex flex-wrap gap-2">
            {selectedDates
              .sort((a, b) => a - b)
              .map((date, index) => (
                <div
                  key={index}
                  className="flex items-center gap-1.5 bg-blue-50 text-blue-700 px-2 py-1 rounded-md text-xs border border-blue-100"
                >
                  <span>{formatDate(date)}</span>
                  <button
                    onClick={() => removeDate(date)}
                    className="hover:bg-blue-100 rounded p-0.5 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}