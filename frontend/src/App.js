import React, { useState, useEffect } from 'react';
import { Home, Plus, X, Loader, LayoutList, Layers } from 'lucide-react';
import ClassificationFilter from './components/ClassificationFilter';
import MultiDayCalendar from './components/MultiDayCalendar';
import DayPicker from './components/DayPicker';
import EventCard from './components/EventCard';
import AddEvent from './components/AddEvent';
import SearchBar from './components/SearchBar';
import './App.css';

// Simple Modal Component
const Modal = ({ isOpen, onClose, title, children }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm transition-opacity">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden transform transition-all">
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-full">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        <div className="p-6">
          {children}
        </div>
      </div>
    </div>
  );
};

function App() {
  const [selectedFilters, setSelectedFilters] = useState({
    topicLabels: [],
    bookmarked: false,
    showPaid: false // Default: Do not show paid events
  });
  const [topicOptions, setTopicOptions] = useState([]);
  const [selectedDates, setSelectedDates] = useState([]);
  const [selectedDays, setSelectedDays] = useState(new Set());
  const [allEvents, setAllEvents] = useState([]);
  const [filteredEvents, setFilteredEvents] = useState([]);
  const [view, setView] = useState('home');
  const [isLoading, setIsLoading] = useState(false);
  
  // View Mode: 'stacked' (grouped by day) or 'list' (flat list sorted by relevance)
  const [viewMode, setViewMode] = useState('stacked');

  // Search State
  const [searchQuery, setSearchQuery] = useState('');
  
  // Bookmark Modal State
  const [bookmarkModalOpen, setBookmarkModalOpen] = useState(false);
  const [pendingBookmarkEventId, setPendingBookmarkEventId] = useState(null);

  const hasPaidPricing = (pricing) => {
    if (!pricing) return false;

    let parsedPricing = pricing;
    if (typeof pricing === 'string') {
      const trimmed = pricing.trim();
      if (!trimmed) return false;

      if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
        try {
          parsedPricing = JSON.parse(trimmed);
        } catch {
          // Fallback for non-JSON text values such as "$1300" or "paid".
          const lower = trimmed.toLowerCase();
          if (lower.includes('paid')) return true;
          const amountMatch = trimmed.match(/\d+(?:\.\d+)?/);
          return Boolean(amountMatch && Number(amountMatch[0]) > 0);
        }
      } else {
        const lower = trimmed.toLowerCase();
        if (lower.includes('free')) return false;
        if (lower.includes('paid')) return true;
        const amountMatch = trimmed.match(/\d+(?:\.\d+)?/);
        return Boolean(amountMatch && Number(amountMatch[0]) > 0);
      }
    }

    const pricingList = Array.isArray(parsedPricing) ? parsedPricing : [parsedPricing];
    return pricingList.some((option) => {
      const value = Number(option?.price ?? 0);
      return Number.isFinite(value) && value > 0;
    });
  };

  // Effect to switch view mode based on search status
  useEffect(() => {
    if (searchQuery) {
      setViewMode('list');
    } else {
      setViewMode('stacked');
    }
  }, [searchQuery]);

  useEffect(() => {
    fetch('http://localhost:8001/topics')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setTopicOptions(data);
        }
      })
      .catch(err => console.error('Error fetching topics:', err));
  }, []);

  // Fetch all events once or when non-distance filters change
  useEffect(() => {
    const params = new URLSearchParams();
    
    // Add topics
    selectedFilters.topicLabels.forEach(topic => params.append('topic', topic));

    // Add bookmarked
    if (selectedFilters.bookmarked) {
      params.append('bookmarked', 'true');
    }
    
    // Add search query
    if (searchQuery) {
      params.append('query', searchQuery);
    }

    setIsLoading(true);
    fetch(`http://localhost:8001/events/all?${params.toString()}`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setAllEvents(data);
        } else {
          console.error("Received non-array data:", data);
          setAllEvents([]);
        }
      })
      .catch(err => console.error('Error fetching events:', err))
      .finally(() => setIsLoading(false));

  }, [selectedFilters.topicLabels, selectedFilters.bookmarked, searchQuery]); // Exclude selectedFilters.showPaid from fetch dep, handle on client

  // Filter events client-side
  useEffect(() => {
    if (allEvents.length === 0) {
      setFilteredEvents([]);
      return;
    }

    const filtered = allEvents.filter(event => {
      // Paid/Free Filter
      // If showPaid is false, ONLY show Free events
      if (!selectedFilters.showPaid) {
        if (hasPaidPricing(event.pricing)) return false;
      }
      
      return true;
    });
    
    setFilteredEvents(filtered);
  }, [allEvents, selectedFilters.showPaid]);

  // Filter events client-side based on Date/Weekday selection
  const visibleEvents = React.useMemo(() => {
      if (selectedDates.length === 0 && selectedDays.size === 0) {
          return filteredEvents;
      }
      return filteredEvents.filter(item => {
          if (!item.start_at) return false;
          
          const d = new Date(item.start_at);
          
          // Check specific dates
          const dateMatch = selectedDates.some(sd => 
              sd.getFullYear() === d.getFullYear() &&
              sd.getMonth() === d.getMonth() &&
              sd.getDate() === d.getDate()
          );

          if (dateMatch) return true;

          // Check weekdays
          // 'Mon', 'Tue' -> 'mon', 'tue'
          const dayName = d.toLocaleDateString('en-US', { weekday: 'short' }).toLowerCase();
          if (selectedDays.has(dayName)) return true;
          
          return false;
      });
  }, [filteredEvents, selectedDates, selectedDays]);

  const handleFilterChange = (category, values) => {
    setSelectedFilters(prev => ({
      ...prev,
      [category]: values
    }));
  };

  const bookmarkEvent = (id, isBookmarked) => {
    // Optimistic update for home list
    setAllEvents(prevEvents => {
      const updated = prevEvents.map(event => 
        event.id === id ? { ...event, bookmarked: isBookmarked } : event
      );
      // Remove from list if viewing bookmarks only and unbookmarking
      if (selectedFilters.bookmarked && !isBookmarked) {
        return updated.filter(e => e.id !== id);
      }
      return updated;
    });

    fetch(`http://localhost:8001/events/${id}/bookmark?bookmarked=${isBookmarked}`, {
      method: 'POST'
    })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        console.error('Error bookmarking event:', data.error);
        // Revert on error
        setAllEvents(prevEvents => prevEvents.map(event => 
          event.id === id ? { ...event, bookmarked: !isBookmarked } : event
        ));
      }
    })
    .catch(err => {
      console.error('Error bookmarking event:', err);
      // Revert on error
      setAllEvents(prevEvents => prevEvents.map(event => 
        event.id === id ? { ...event, bookmarked: !isBookmarked } : event
      ));
    });
  };

  const handleBookmark = (id, isBookmarked) => {
    bookmarkEvent(id, isBookmarked);
  };
  
  const handleViewEvent = (event) => {
      if (!event.bookmarked) {
          setPendingBookmarkEventId(event.id);
          setBookmarkModalOpen(true);
      }
  };

  const confirmBookmark = () => {
      if (pendingBookmarkEventId) {
          bookmarkEvent(pendingBookmarkEventId, true);
      }
      setBookmarkModalOpen(false);
      setPendingBookmarkEventId(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        <header className="mb-8 relative flex items-center justify-center">
          <button 
            onClick={() => setView('home')}
            className={`absolute left-0 p-3 rounded-full transition-colors ${
              view === 'home' 
                ? 'bg-blue-600 text-white shadow-md' 
                : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
            }`}
            aria-label="Home"
          >
            <Home className="w-5 h-5" />
          </button>

          <h1 className="text-3xl font-bold text-gray-900">Luma Event Aggregation</h1>
          
          <button 
            onClick={() => setView('add-event')}
            className={`absolute right-0 p-3 rounded-full transition-colors ${
              view === 'add-event' 
                ? 'bg-blue-600 text-white shadow-md' 
                : 'bg-white text-blue-600 hover:bg-gray-50 border border-gray-200'
            }`}
            aria-label="Add Event"
          >
            <Plus className="w-5 h-5" />
          </button>
        </header>

        {view === 'home' && (
          <>
            <div className="mb-6 flex flex-col md:flex-row gap-4 justify-center items-center">
                <SearchBar onSearch={setSearchQuery} />
                
                {/* View Toggle */}
                <div className="flex bg-white rounded-lg shadow-sm border border-gray-200 p-1">
                    <button
                        onClick={() => setViewMode('stacked')}
                        className={`p-2 rounded-md transition-colors ${
                            viewMode === 'stacked' 
                                ? 'bg-indigo-100 text-indigo-700' 
                                : 'text-gray-500 hover:bg-gray-50'
                        }`}
                        title="Group by Date"
                    >
                        <Layers className="w-5 h-5" />
                    </button>
                    <button
                        onClick={() => setViewMode('list')}
                        className={`p-2 rounded-md transition-colors ${
                            viewMode === 'list' 
                                ? 'bg-indigo-100 text-indigo-700' 
                                : 'text-gray-500 hover:bg-gray-50'
                        }`}
                        title="List by Relevance"
                    >
                        <LayoutList className="w-5 h-5" />
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Sidebar - Filters */}
              <div className="lg:col-span-8">
                 <MultiDayCalendar 
                  selectedDates={selectedDates}
                  onDatesChange={setSelectedDates}
                  events={filteredEvents}
                />
              </div>
              
              {/* Event Classifications */}
              <div className="lg:col-span-4 space-y-4">
                <ClassificationFilter 
                  selectedFilters={selectedFilters}
                  onFilterChange={handleFilterChange}
                  topicOptions={topicOptions.filter(t => t.label && t.label !== 'nan' && t.label !== 'none')}
                />
                
                <DayPicker 
                  selectedDays={selectedDays}
                  onDaysChange={setSelectedDays}
                />
              </div>
            </div>

            <div className="mt-12">
              {isLoading ? (
                  <div className="flex justify-center items-center h-64">
                    <Loader className="w-12 h-12 animate-spin text-indigo-600" />
                  </div>
              ) : (
                  <EventCard 
                    events={visibleEvents} 
                    onBookmark={handleBookmark} 
                    onViewEvent={handleViewEvent}
                    isSearching={!!searchQuery} // Pass search state
                    viewMode={viewMode}
                  />
              )}
            </div>
          </>
        )}

        {view === 'add-event' && (
          <AddEvent 
            onEventAdded={(newEvent) => {
              setAllEvents(prev => [...prev, newEvent]);
              setView('home');
            }}
            onCancel={() => setView('home')}
          />
        )}
        
        {/* Bookmark Prompt Modal */}
        <Modal 
            isOpen={bookmarkModalOpen} 
            onClose={() => setBookmarkModalOpen(false)}
            title="Bookmark this event?"
        >
            <p className="text-gray-600 mb-6">
                You just viewed this event on Luma. Would you like to add it to your bookmarks for easier access later?
            </p>
            <div className="flex justify-end gap-3">
                <button 
                    onClick={() => setBookmarkModalOpen(false)}
                    className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm font-medium transition-colors"
                >
                    No thanks
                </button>
                <button 
                    onClick={confirmBookmark}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors shadow-sm"
                >
                    Yes, Bookmark
                </button>
            </div>
        </Modal>
      </div>
    </div>
  );
}

export default App;