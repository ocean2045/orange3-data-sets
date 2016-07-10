
import logging
from functools import partial

from functools import lru_cache

from PyQt4.QtCore import Qt, QThread, QCoreApplication


from PyQt4 import QtGui
from PyQt4 import QtCore
from Orange.widgets import gui
from Orange.widgets.utils import concurrent

from Orange.widgets.gui import LinkRole

TextFilterRole = next(gui.OrangeUserRole)
logger = logging.getLogger(__name__)


class MySortFilterProxyModel(QtGui.QSortFilterProxyModel):

    def __init__(self, parent=None):
        QtGui.QSortFilterProxyModel.__init__(self, parent)
        self._filter_strings = []
        self._cache = {}
        self._cache_fixed = {}
        self._cache_prefix = {}
        self._row_text = {}

        # Create a cached version of _filteredRows
        self._filteredRows = lru_cache(100)(self._filteredRows)

    def setSourceModel(self, model):
        """Set the source model for the filter.
        """
        self._filter_strings = []
        self._cache = {}
        self._cache_fixed = {}
        self._cache_prefix = {}
        self._row_text = {}
        QtGui.QSortFilterProxyModel.setSourceModel(self, model)

    def addFilterFixedString(self, string, invalidate=True):
        """ Add `string` filter to the list of filters. If invalidate is
        True the filter cache will be recomputed.
        """
        self._filter_strings.append(string)
        all_rows = range(self.sourceModel().rowCount())
        row_text = [self.rowFilterText(row) for row in all_rows]
        self._cache[string] = [string in text for text in row_text]
        if invalidate:
            self.updateCached()
            self.invalidateFilter()

    def removeFilterFixedString(self, index=-1, invalidate=True):
        """ Remove the `index`-th filter string. If invalidate is True the
        filter cache will be recomputed.
        """
        string = self._filter_strings.pop(index)
        del self._cache[string]
        if invalidate:
            self.updateCached()
            self.invalidate()

    def setFilterFixedStrings(self, strings):
        """Set a list of string to be the new filters.
        """
        to_remove = set(self._filter_strings) - set(strings)
        to_add = set(strings) - set(self._filter_strings)
        for str in to_remove:
            self.removeFilterFixedString(
                self._filter_strings.index(str),
                invalidate=False)

        for str in to_add:
            self.addFilterFixedString(str, invalidate=False)
        self.updateCached()
        self.invalidate()

    def _filteredRows(self, filter_strings):
        """Return a dictionary mapping row indexes to True False values.

        .. note:: This helper function is wrapped in the __init__ method.

        """
        all_rows = range(self.sourceModel().rowCount())
        cache = self._cache
        return dict([(row, all([cache[str][row] for str in filter_strings]))
                     for row in all_rows])

    def updateCached(self):
        """Update the combined filter cache.
        """
        self._cache_fixed = self._filteredRows(
            tuple(sorted(self._filter_strings)))

    def setFilterFixedString(self, string):
        """Should this raise an error? It is not being used.
        """
        QtGui.QSortFilterProxyModel.setFilterFixedString(self, string)

    def rowFilterText(self, row):
        """Return text for `row` to filter on.
        """
        f_role = self.filterRole()
        f_column = self.filterKeyColumn()
        s_model = self.sourceModel()
        data = s_model.data(s_model.index(row, f_column), f_role)
        return str(data)

    def filterAcceptsRow(self, row, parent):
        return self._cache_fixed.get(row, True)

    def lessThan(self, left, right):
        # TODO: Remove fixed column handling
        if left.column() == 1 and right.column():
            left_gds = str(left.data(Qt.DisplayRole))
            right_gds = str(right.data(Qt.DisplayRole))
            left_gds = left_gds.lstrip("GDS")
            right_gds = right_gds.lstrip("GDS")
            try:
                return int(left_gds) < int(right_gds)
            except ValueError:
                pass
        return QtGui.QSortFilterProxyModel.lessThan(self, left, right)


class IndicatorsTreeView(QtGui.QTreeView):

    def __init__(self, parent, main_widget=None):
        super().__init__(parent)
        self._main_widget = main_widget
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QtGui.QTreeView.NoEditTriggers)
        self.setRootIsDecorated(False)
        self.setSortingEnabled(True)
        self.setUniformRowHeights(True)
        self.viewport().setMouseTracking(True)

        proxyModel = MySortFilterProxyModel(self)
        self.setModel(proxyModel)
        self.selectionModel().selectionChanged.connect(
            self.updateSelection
        )
        self.viewport().setMouseTracking(True)

        self._executor = concurrent.ThreadExecutor()

        func = partial(self._fetch_indicators,
                       concurrent.methodinvoke(self, "_setProgress", (float,)))
        self._fetch_task = concurrent.Task(function=func)
        self._fetch_task.finished.connect(self._fetch_indicators_finished)
        self._fetch_task.exceptionReady.connect(self._init_exception)

        self._main_widget.setBlocking(True)
        self._main_widget.setEnabled(False)
        self._executor.submit(self._fetch_task)

    def updateSelection(self):
        pass

    def _fetch_indicators(self, progress=lambda val: None):

        def item(displayvalue, item_values={}):
            item = QtGui.QStandardItem()
            item.setData(displayvalue, Qt.DisplayRole)
            item.setData("https" + displayvalue, LinkRole)
            return item

        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(["", "ID", "Title", "description"])
        model.appendRow([item(""), item("item 1"), item("2"), ])
        model.appendRow([item(" "), item("item 3 ua"), item(
            "oauoe aotuhounotahunoa huoa nuthoea utoanhu oanehuoa"
            "oauoe aotuhounotahunoa huoa nuthoea utoanhu oanehuoa"
            "oauoe aotuhounotahunoa huoa nuthoea utoanhu oanehuoa"
            "usaohu soatehu oanuhtao suhtoa suhoaesuthoasuntoehuso9"), ])
        model.appendRow([item(""), item("some"), item("3"), ])
        model.appendRow([item(" "), item("thing"), item("4 ouoeauaouoau"), ])
        model.appendRow([item(" "), item("else 6"), item("7"), ])
        model.appendRow([item(" "), item("else 7"), item("14"), ])
        model.appendRow([item(" "), item("else 8"), item("7"), ])
        model.appendRow([item(" "), item("else 10"), item("7"), ])
        model.appendRow([item(" "), item("else 13"), item("10"), ])
        model.appendRow([item(" "), item("else 9"), item("7"), ])

        if QThread.currentThread() is not QCoreApplication.instance().thread():
            model.moveToThread(QCoreApplication.instance().thread())

        return model

    def _init_exception(self):
        pass

    def _fetch_indicators_finished(self):
        assert self.thread() is QtCore.QThread.currentThread()
        model = self._fetch_task.result()
        model.setParent(self)

        proxy = self.model()
        proxy.setFilterKeyColumn(0)
        proxy.setFilterRole(TextFilterRole)
        proxy.setFilterCaseSensitivity(False)
        # proxy.setFilterFixedString(self.filterString)

        proxy.setSourceModel(model)
        proxy.sort(1, QtCore.Qt.DescendingOrder)

        # self.progressBarFinished()

        self._main_widget.setBlocking(False)
        self._main_widget.setEnabled(True)

        for i in range(3):
            self.resizeColumnToContents(i)

        self.setColumnWidth(
            1, min(self.columnWidth(1), 300))
        self.setColumnWidth(
            2, min(self.columnWidth(2), 400))
