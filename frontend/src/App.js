import React, { useState, useEffect } from 'react';
import { Home, Plus, X, Loader, LayoutList, Layers, Calendar } from 'lucide-react';
import ClassificationFilter from './components/ClassificationFilter';
import MultiDayCalendar from './components/MultiDayCalendar';
import DayPicker from './components/DayPicker';
import EventCard from './components/EventCard';
import AddEvent from './components/AddEvent';
import SearchBar from './components/SearchBar';
import './App.css';

let hasFetchedAllEvents = false;

const isValidTopicLabel = (label) => {
  if (typeof label !== 'string') return false;
  const normalized = label.trim().toLowerCase();
  return normalized !== '' && normalized !== 'nan' && normalized !== 'none';
};

const getEventStartTimestamp = (event) => {
  const startAt = event?.start_at ?? event?.event?.start_at;
  if (!startAt) return null;

  const parsedStart = new Date(startAt);
  const timestamp = parsedStart.getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
};

const isEventStartAtOrBeforeCutoff = (event, cutoffTimestamp) => {
  const startTimestamp = getEventStartTimestamp(event);
  if (startTimestamp === null) return false;
  return startTimestamp <= cutoffTimestamp;
};

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
  const [bookmarkedCategoryFilterActive, setBookmarkedCategoryFilterActive] = useState(false);
  const [allEvents, setAllEvents] = useState([]);
  const [view, setView] = useState('home');
  const [isLoading, setIsLoading] = useState(false);
  const [pageLoadTime] = useState(() => Date.now());
  
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

  const matchesSearchQuery = (event, query) => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return true;

    const searchableParts = [
      event?.name,
      event?.description,
      event?.city,
      event?.topic_label,
    ]
      .filter((value) => typeof value === 'string' && value.trim())
      .map((value) => value.toLowerCase());

    return searchableParts.some((value) => value.includes(normalizedQuery));
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

  const presentEvents = React.useMemo(() => {
    return allEvents.filter((event) => !isEventStartAtOrBeforeCutoff(event, pageLoadTime));
  }, [allEvents, pageLoadTime]);

  const bookmarkedTopicLabels = React.useMemo(() => {
    const labels = new Set();

    presentEvents.forEach((event) => {
      if (!event?.bookmarked) return;

      const label = event?.topic_label;
      if (!isValidTopicLabel(label)) return;

      labels.add(label);
    });

    return Array.from(labels).sort((a, b) => a.localeCompare(b));
  }, [presentEvents]);

  const effectiveTopicLabels = React.useMemo(() => {
    const labels = new Set(selectedFilters.topicLabels);

    if (bookmarkedCategoryFilterActive) {
      bookmarkedTopicLabels.forEach((label) => labels.add(label));
    }

    return Array.from(labels);
  }, [bookmarkedCategoryFilterActive, bookmarkedTopicLabels, selectedFilters.topicLabels]);

  const handleBookmarkedCategoriesToggle = () => {
    setBookmarkedCategoryFilterActive((current) => !current);
  };

  const filteredEvents = React.useMemo(() => {
    return presentEvents.filter((event) => {
      if (!matchesSearchQuery(event, searchQuery)) {
        return false;
      }

      if (!selectedFilters.showPaid && hasPaidPricing(event.pricing)) {
        return false;
      }

      if (selectedFilters.bookmarked && !event.bookmarked) {
        return false;
      }

      if (effectiveTopicLabels.length > 0 && !effectiveTopicLabels.includes(event.topic_label)) {
        return false;
      }

      return true;
    });
  }, [effectiveTopicLabels, presentEvents, searchQuery, selectedFilters.bookmarked, selectedFilters.showPaid]);

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

  // Compute topic options from events filtered by search/bookmarks/paid/date, but BEFORE topic selection
  // This keeps all clusters visible in the sidebar even when one is selected
  const eventsBeforeTopicFilter = React.useMemo(() => {
    return presentEvents.filter((event) => {
      if (!matchesSearchQuery(event, searchQuery)) {
        return false;
      }

      if (!selectedFilters.showPaid && hasPaidPricing(event.pricing)) {
        return false;
      }

      if (selectedFilters.bookmarked && !event.bookmarked) {
        return false;
      }

      // Apply date/day filters (same logic as visibleEvents)
      if (selectedDates.length === 0 && selectedDays.size === 0) {
        return true;
      }

      if (!event.start_at) return false;

      const d = new Date(event.start_at);

      const dateMatch = selectedDates.some(sd => 
        sd.getFullYear() === d.getFullYear() &&
        sd.getMonth() === d.getMonth() &&
        sd.getDate() === d.getDate()
      );

      if (dateMatch) return true;

      const dayName = d.toLocaleDateString('en-US', { weekday: 'short' }).toLowerCase();
      return selectedDays.has(dayName);
    });
  }, [presentEvents, searchQuery, selectedFilters.bookmarked, selectedFilters.showPaid, selectedDates, selectedDays]);

  const displayTopicOptions = React.useMemo(() => {

    const countByLabel = new Map();

    eventsBeforeTopicFilter.forEach((event) => {
      const label = event?.topic_label;
      if (!isValidTopicLabel(label)) return;
      countByLabel.set(label, (countByLabel.get(label) || 0) + 1);
    });

    const colorByLabel = new Map();
    topicOptions.forEach((topic) => {
      if (isValidTopicLabel(topic?.label)) {
        colorByLabel.set(topic.label, topic.color || '#64748B');
      }
    });

    eventsBeforeTopicFilter.forEach((event) => {
      const label = event?.topic_label;
      if (!isValidTopicLabel(label)) return;
      if (!colorByLabel.has(label)) {
        colorByLabel.set(label, event?.topic_color || '#64748B');
      }
    });

    const labels = new Set([...colorByLabel.keys(), ...countByLabel.keys()]);

    return Array.from(labels)
      .map((label) => ({
        label,
        color: colorByLabel.get(label) || '#64748B',
        count: countByLabel.get(label) || 0,
      }))
      .filter((topic) => topic.count > 0)
      .sort((a, b) => {
        if (b.count !== a.count) return b.count - a.count;
        return a.label.localeCompare(b.label);
      });
  }, [topicOptions, eventsBeforeTopicFilter]);

  // Fetch all events once when the page is entered.
  useEffect(() => {
    if (hasFetchedAllEvents) {
      return;
    }

    hasFetchedAllEvents = true;

    const params = new URLSearchParams();

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

  }, []);

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
    <div className={`h-screen bg-gradient-to-br from-blue-50 to-indigo-50 ${view === 'home' ? 'overflow-hidden' : 'overflow-y-auto'}`}>
      <div className="w-full max-w-[1800px] mx-auto px-4 py-6 h-full flex flex-col overflow-hidden">
        <header className="mb-8 relative flex items-center justify-center shrink-0">
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
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start text-[13px] flex-1 min-h-0 overflow-hidden">
              <aside className="lg:col-span-3 bg-white/70 border border-gray-200 rounded-xl p-4 space-y-4 h-full min-h-0 overflow-y-auto">
                <div className="flex items-center gap-2 p-3 rounded-lg border border-gray-200 bg-white">
                  <Calendar className="w-4 h-4 text-indigo-600" />
                  <span className="text-sm font-semibold text-gray-800">Filter by Date</span>
                </div>

                <div className="space-y-3">
                  <DayPicker 
                    selectedDays={selectedDays}
                    onDaysChange={setSelectedDays}
                  />

                  <MultiDayCalendar 
                    selectedDates={selectedDates}
                    onDatesChange={setSelectedDates}
                    events={filteredEvents}
                  />
                </div>

                <ClassificationFilter 
                  selectedFilters={selectedFilters}
                  onFilterChange={handleFilterChange}
                  bookmarkedCategoriesActive={bookmarkedCategoryFilterActive}
                  bookmarkedTopicLabels={bookmarkedTopicLabels}
                  onBookmarkedCategoriesToggle={handleBookmarkedCategoriesToggle}
                  topicOptions={displayTopicOptions}
                />
              </aside>

              <section className="lg:col-span-9 h-full min-h-0 overflow-y-auto pr-1">
                <div className="sticky top-0 z-20 bg-blue-50/90 backdrop-blur-sm pb-4 mb-4">
                  <div className="flex flex-col md:flex-row gap-3 justify-between items-stretch md:items-center">
                    <SearchBar onSearch={setSearchQuery} className="max-w-full md:max-w-xl" />

                    <div className="flex bg-white rounded-lg shadow-sm border border-gray-200 p-1 self-end md:self-auto">
                      <button
                        onClick={() => setViewMode('stacked')}
                        className={`p-2 rounded-md transition-colors ${
                          viewMode === 'stacked' 
                            ? 'bg-indigo-100 text-indigo-700' 
                            : 'text-gray-500 hover:bg-gray-50'
                        }`}
                        title="Group by Date"
                      >
                        <Layers className="w-4 h-4" />
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
                        <LayoutList className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>

                {isLoading ? (
                  <div className="flex justify-center items-center h-64">
                    <Loader className="w-12 h-12 animate-spin text-indigo-600" />
                  </div>
                ) : (
                  <EventCard 
                    events={visibleEvents} 
                    onBookmark={handleBookmark} 
                    onViewEvent={handleViewEvent}
                    isSearching={!!searchQuery}
                    viewMode={viewMode}
                  />
                )}
              </section>
            </div>
          </>
        )}

        {view === 'add-event' && (
          <div className="flex-1 min-h-0 overflow-y-auto">
            <AddEvent 
              onEventAdded={(newEvent) => {
                setAllEvents(prev => [...prev, newEvent]);
                setView('home');
              }}
              onCancel={() => setView('home')}
            />
          </div>
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