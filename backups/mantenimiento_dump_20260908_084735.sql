PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE maquinas (
	id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	codigo VARCHAR(50) NOT NULL, 
	serial VARCHAR(50), 
	modelo VARCHAR(100), 
	marca VARCHAR(100), 
	ubicacion VARCHAR(200), 
	fecha_compra DATE, 
	fecha_instalacion DATE, 
	proveedor VARCHAR(100), 
	estado VARCHAR(20), 
	observaciones TEXT, 
	fecha_registro DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	UNIQUE (serial)
);
INSERT INTO maquinas VALUES(1,'SIERRA ACOLILLADORA','ING-01','None','DWS713-B3A','DeWalt','Zona de cortes','2023-06-27','2023-06-28',' BELLTEC SAS','Operativa','La maquina está bien y lista para operar','2026-07-29 15:03:42.154335');
INSERT INTO maquinas VALUES(2,'SIERRA ACOLILLADORA 2','ING-02','','DWS713-B3A','DeWalt','Zona de cortes','2023-12-12','2023-12-13',' BELLTEC SAS','Operativa','','2026-07-29 15:08:54.278141');
INSERT INTO maquinas VALUES(3,'Maquina de soldadura de aluminio','SOL-ALU-01','000','eliteMP220','ELITE','Laboratorio','2026-09-08','2026-09-08',' BELLTEC SAS','Operativa','La maquina está operativa y depende del gas argón ARGON-01 y ARGON-02','2026-09-08 13:37:36.772024');
INSERT INTO maquinas VALUES(4,'Tanque de Argón #1','ARGON-01','0000','N-A','MESSER','Laboratorio','2026-09-08','2026-09-08','Na','Operativa','Se deben mandar a llenar según el uso que se le de ','2026-09-08 13:39:18.687250');
INSERT INTO maquinas VALUES(5,'Tanque de Argón #2','ARGON-02','00000','N-A','MESSER','Laboratorio','2026-09-08','2026-09-08','N/a','Operativa','Se deben mandar a llenar según el uso que se le de ','2026-09-08 13:44:33.575339');
CREATE TABLE mantenimientos (
	id INTEGER NOT NULL, 
	maquina_id INTEGER NOT NULL, 
	tipo VARCHAR(20) NOT NULL, 
	fecha DATETIME, 
	tecnico VARCHAR(100) NOT NULL, 
	departamento VARCHAR(100), 
	descripcion TEXT NOT NULL, 
	repuestos TEXT, 
	observaciones TEXT, 
	duracion FLOAT, 
	prioridad VARCHAR(20), 
	fecha_proximo DATE, 
	estado VARCHAR(20), 
	fecha_registro DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(maquina_id) REFERENCES maquinas (id)
);
INSERT INTO mantenimientos VALUES(1,1,'Preventivo','2026-07-29 21:56:59.270177','Belltec','Zona de cortes','Preventivo','','',192.0,'Media','2026-11-29','En progreso','2026-07-29 21:56:59.270191');
COMMIT;
