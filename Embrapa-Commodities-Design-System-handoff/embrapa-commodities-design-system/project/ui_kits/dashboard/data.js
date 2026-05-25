// Fake data for the commodity dashboard mock. Shape matches gold_commodity_matrix.

window.PRODUCTS = [
  { code: '49101', name: 'Castanha-do-pará', unit: 't' },
  { code: '49103', name: 'Açaí (fruto)',     unit: 't' },
  { code: '49108', name: 'Erva-mate',        unit: 't' },
  { code: '49112', name: 'Pinhão',           unit: 't' },
  { code: '49215', name: 'Madeira em tora',  unit: 'm³' },
  { code: '49216', name: 'Lenha',            unit: 'm³' },
  { code: '49218', name: 'Carvão vegetal',   unit: 't' },
  { code: '49221', name: 'Borracha (látex)', unit: 't' },
];

// Time series: year + val_real_ipca_brl (BRL real, billions) + quantity (kt) for "all products"
window.OVERVIEW_TS = [
  { y: 1995, v: 1.42, q: 1832 }, { y: 1996, v: 1.51, q: 1894 },
  { y: 1997, v: 1.63, q: 1980 }, { y: 1998, v: 1.58, q: 2031 },
  { y: 1999, v: 1.71, q: 2120 }, { y: 2000, v: 1.84, q: 2247 },
  { y: 2001, v: 1.92, q: 2356 }, { y: 2002, v: 2.08, q: 2401 },
  { y: 2003, v: 2.27, q: 2389 }, { y: 2004, v: 2.45, q: 2478 },
  { y: 2005, v: 2.51, q: 2502 }, { y: 2006, v: 2.39, q: 2456 },
  { y: 2007, v: 2.62, q: 2531 }, { y: 2008, v: 2.84, q: 2580 },
  { y: 2009, v: 2.71, q: 2492 }, { y: 2010, v: 3.04, q: 2640 },
  { y: 2011, v: 3.22, q: 2698 }, { y: 2012, v: 3.45, q: 2745 },
  { y: 2013, v: 3.32, q: 2701 }, { y: 2014, v: 3.51, q: 2810 },
  { y: 2015, v: 3.27, q: 2658 }, { y: 2016, v: 3.39, q: 2701 },
  { y: 2017, v: 3.58, q: 2780 }, { y: 2018, v: 3.81, q: 2842 },
  { y: 2019, v: 3.97, q: 2901 }, { y: 2020, v: 3.62, q: 2734 },
  { y: 2021, v: 4.12, q: 2980 }, { y: 2022, v: 4.38, q: 3041 },
  { y: 2023, v: 4.21, q: 2952 },
];

// Top UFs (2023)
window.TOP_UFS = [
  { uf: 'PA', name: 'Pará',     value: 982, q: 412 },
  { uf: 'AM', name: 'Amazonas', value: 614, q: 287 },
  { uf: 'MT', name: 'Mato Grosso', value: 538, q: 240 },
  { uf: 'AC', name: 'Acre',     value: 392, q: 184 },
  { uf: 'RO', name: 'Rondônia', value: 287, q: 132 },
  { uf: 'MG', name: 'Minas Gerais', value: 219, q: 98 },
  { uf: 'BA', name: 'Bahia',    value: 184, q: 84 },
  { uf: 'TO', name: 'Tocantins', value: 142, q: 65 },
];

// Top products (2023)
window.TOP_PRODUCTS = [
  { name: 'Madeira em tora',  share: 0.34, value: 1431, color: 'var(--viz-1)' },
  { name: 'Lenha',            share: 0.18, value: 758,  color: 'var(--viz-2)' },
  { name: 'Açaí (fruto)',     share: 0.12, value: 505,  color: 'var(--viz-3)' },
  { name: 'Castanha-do-pará', share: 0.09, value: 379,  color: 'var(--viz-4)' },
  { name: 'Carvão vegetal',   share: 0.08, value: 337,  color: 'var(--viz-5)' },
  { name: 'Erva-mate',        share: 0.07, value: 295,  color: 'var(--viz-7)' },
  { name: 'Outros',           share: 0.12, value: 506,  color: 'var(--pres-gray-200)', muted: true },
];

// Sample table rows — represents recent rows from gold_commodity_matrix
window.SAMPLE_ROWS = [
  { year: 2023, uf: 'PA', city: 'Marabá',        product: 'Castanha-do-pará', qty: 14829, unit: 't',  val_ipca: 82471220, val_yearfx: 78213900, flag: 'OK' },
  { year: 2023, uf: 'AM', city: 'Manaus',        product: 'Castanha-do-pará', qty: 9314,  unit: 't',  val_ipca: 51038910, val_yearfx: 48910420, flag: 'OK' },
  { year: 2023, uf: 'AC', city: 'Rio Branco',    product: 'Castanha-do-pará', qty: 3207,  unit: 't',  val_ipca: null,     val_yearfx: null,     flag: 'MISSING_VALUE' },
  { year: 2023, uf: 'RO', city: 'Porto Velho',   product: 'Castanha-do-pará', qty: 2118,  unit: 't',  val_ipca: 11092480, val_yearfx: 10721090, flag: 'OK' },
  { year: 2023, uf: 'PA', city: 'Santarém',      product: 'Madeira em tora',  qty: 47820, unit: 'm³', val_ipca: 198470100, val_yearfx: 191207800, flag: 'OK' },
  { year: 2023, uf: 'MT', city: 'Sinop',         product: 'Madeira em tora',  qty: 31204, unit: 'm³', val_ipca: 128471000, val_yearfx: 123092600, flag: 'OK' },
  { year: 2023, uf: 'RR', city: 'Caracaraí',     product: 'Madeira em tora',  qty: null,  unit: 'm³', val_ipca: 4218900,  val_yearfx: 4080010,  flag: 'MISSING_QUANTITY' },
];

window.fmtBRL = (n) => {
  if (n == null) return '—';
  if (n >= 1e9) return 'R$ ' + (n / 1e9).toFixed(2).replace('.', ',') + ' bi';
  if (n >= 1e6) return 'R$ ' + (n / 1e6).toFixed(1).replace('.', ',') + ' mi';
  if (n >= 1e3) return 'R$ ' + (n / 1e3).toFixed(0).replace('.', ',') + ' mil';
  return 'R$ ' + n.toLocaleString('pt-BR');
};
window.fmtNum = (n, unit) => {
  if (n == null) return '—';
  return n.toLocaleString('pt-BR') + (unit ? ' ' + unit : '');
};
