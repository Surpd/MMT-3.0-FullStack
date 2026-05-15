export type Movie = {
  id: string;
  title: string;
  year: number;
  rating: number;
  runtime: number;
  genres: string[];
  poster: string;
  plot: string;
  director: string;
};

// High-res posters via TMDB CDN (publicly hosted)
const tmdb = (path: string) => `https://image.tmdb.org/t/p/w780${path}`;

export const MOVIES: Movie[] = [
  {
    id: "m1",
    title: "Dune: Part Two",
    year: 2024,
    rating: 8.6,
    runtime: 166,
    genres: ["Sci-Fi", "Adventure"],
    poster: tmdb("/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg"),
    plot: "Paul Atreides unites with the Fremen and seeks revenge against the conspirators who destroyed his family, all while trying to prevent a terrible future only he can foresee.",
    director: "Denis Villeneuve",
  },
  {
    id: "m2",
    title: "Oppenheimer",
    year: 2023,
    rating: 8.5,
    runtime: 180,
    genres: ["Drama", "Biography"],
    poster: tmdb("/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg"),
    plot: "A dramatization of the life story of J. Robert Oppenheimer, the physicist who had a large hand in the development of the atomic bombs that brought an end to World War II.",
    director: "Christopher Nolan",
  },
  {
    id: "m3",
    title: "Blade Runner 2049",
    year: 2017,
    rating: 8.0,
    runtime: 164,
    genres: ["Sci-Fi", "Noir"],
    poster: tmdb("/gajva2L0rPYkEWjzgFlBXCAVBE5.jpg"),
    plot: "Young Blade Runner K's discovery of a long-buried secret leads him to track down former Blade Runner Rick Deckard, who's been missing for thirty years.",
    director: "Denis Villeneuve",
  },
  {
    id: "m4",
    title: "Everything Everywhere All at Once",
    year: 2022,
    rating: 7.8,
    runtime: 139,
    genres: ["Sci-Fi", "Comedy"],
    poster: tmdb("/w3LxiVYdWWRvEVdn5RYq6jIqkb1.jpg"),
    plot: "A middle-aged Chinese immigrant is swept up into an insane adventure in which she alone can save existence by exploring other universes and connecting with the lives she could have led.",
    director: "Daniels",
  },
  {
    id: "m5",
    title: "The Batman",
    year: 2022,
    rating: 7.8,
    runtime: 176,
    genres: ["Action", "Crime"],
    poster: tmdb("/74xTEgt7R36Fpooo50r9T25onhq.jpg"),
    plot: "When a sadistic serial killer begins murdering key political figures in Gotham, Batman is forced to investigate the city's hidden corruption and question his family's involvement.",
    director: "Matt Reeves",
  },
  {
    id: "m6",
    title: "Parasite",
    year: 2019,
    rating: 8.5,
    runtime: 132,
    genres: ["Thriller", "Drama"],
    poster: tmdb("/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg"),
    plot: "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.",
    director: "Bong Joon-ho",
  },
  {
    id: "m7",
    title: "Interstellar",
    year: 2014,
    rating: 8.7,
    runtime: 169,
    genres: ["Sci-Fi", "Drama"],
    poster: tmdb("/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg"),
    plot: "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
    director: "Christopher Nolan",
  },
  {
    id: "m8",
    title: "Mad Max: Fury Road",
    year: 2015,
    rating: 8.1,
    runtime: 120,
    genres: ["Action", "Adventure"],
    poster: tmdb("/8tZYtuWezp8JbcsvHYO0O46tFbo.jpg"),
    plot: "In a post-apocalyptic wasteland, a woman rebels against a tyrannical ruler in search for her homeland with the aid of a group of female prisoners.",
    director: "George Miller",
  },
  {
    id: "m9",
    title: "Arrival",
    year: 2016,
    rating: 7.9,
    runtime: 116,
    genres: ["Sci-Fi", "Drama"],
    poster: tmdb("/x2FJsf1ElAgr63Y3PNPtJrcmpoe.jpg"),
    plot: "A linguist works with the military to communicate with alien lifeforms after twelve mysterious spacecraft appear around the world.",
    director: "Denis Villeneuve",
  },
  {
    id: "m10",
    title: "The Grand Budapest Hotel",
    year: 2014,
    rating: 8.1,
    runtime: 99,
    genres: ["Comedy", "Drama"],
    poster: tmdb("/eWdyYQreja6JGCzqHWXpWHDrrPo.jpg"),
    plot: "A writer encounters the owner of an aging high-class hotel, who tells him of his early years serving as a lobby boy in the hotel's glorious years under an exceptional concierge.",
    director: "Wes Anderson",
  },
  {
    id: "m11",
    title: "Whiplash",
    year: 2014,
    rating: 8.5,
    runtime: 106,
    genres: ["Drama", "Music"],
    poster: tmdb("/7fn624j5lj3xTme2SgiLCeuedmO.jpg"),
    plot: "A promising young drummer enrolls at a cut-throat music conservatory where his dreams of greatness are mentored by an instructor who will stop at nothing to realize a student's potential.",
    director: "Damien Chazelle",
  },
  {
    id: "m12",
    title: "John Wick: Chapter 4",
    year: 2023,
    rating: 7.7,
    runtime: 169,
    genres: ["Action", "Thriller"],
    poster: tmdb("/vZloFAK7NmvMGKE7VkF5UHaz0I.jpg"),
    plot: "John Wick uncovers a path to defeating The High Table. But before he can earn his freedom, Wick must face off against a new enemy with powerful alliances.",
    director: "Chad Stahelski",
  },
];

export const ALL_GENRES = Array.from(
  new Set(MOVIES.flatMap((m) => m.genres))
).sort();
