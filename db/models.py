from sqlalchemy import Column, ForeignKey, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class Serial(Base):
    __tablename__ = 'serial'
    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True)
    # backref добавляет в объект Series атрибут serial, который ссылается на
    # родительский объект
    all_series = relationship('Series', backref='serial')

    def __repr__(self):
        return 'Сериал <{}>'.format(self.name)

    def __str__(self):
        return 'Сериал <{}>'.format(self.name)


class Series(Base):
    __tablename__ = 'series'
    id = Column(Integer, primary_key=True)
    id_serial = Column(Integer, ForeignKey('serial.id'))
    series_number = Column(Integer)
    season_number = Column(Integer)
    looked = Column(Boolean(), default=False)

    def __repr__(self):
        return '{} (сезон {}, серия {})'.format(self.serial.name,
                                                self.season_number,
                                                self.series_number)

    def __str__(self):
        return '{} (сезон {}, серия {})'.format(self.serial.name,
                                                self.season_number,
                                                self.series_number)
