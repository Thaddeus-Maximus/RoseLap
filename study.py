from sim import *
import vehicle
import track_segmentation
#import fancyyaml as yaml
import json as yaml

"""
Study Schema:
vehicle: [string] filename for .json in the Vehicles directory
track: [string] filename for .dxf in the DXFs directory
segment_distance: [float]
tests: [object-array]
	target: [string] vehicle parameter to alter
	operation: 'replace' || 'product' || 'inverse-product'
	test_vals: [float-array]
plot_style: 'semilog' || 'basic'
plot_title: [string]
plot_x_label: [string]
plot_y_label: [string]
plot_points: [float-array]
"""

def testPointToMatrixValue():
	def getval(t, t2):
		times[test_points.index(t), test_points2.index(t2)]
	return getval

class StudyRecord:
	def __init__(self, times, segList, sobj, kind="2D"):
		self.times = times
		self.segList = segList
		self.sobj = sobj
		self.kind = kind

		for key in sobj:
			setattr(self, key, sobj[key])

	def plot(self):
		print("Plotting results...")

		if self.kind == "2D":
			# plot the study
			fig, ax = plt.subplots()

			for i, track in enumerate(self.track):
				title = self.plot_title + " for " + track + " at mesh size " + str(self.segment_distance[i])

				if self.plot_style == "basic":
					ax.plot(self.plot_points, self.times[i], label=title, marker='x', linestyle='-')
				elif self.plot_style == "semilog":
					ax.semilogx(self.plot_points, self.times[i], label=title, marker='x', linestyle='-')

			ax.grid(True)
			ax.legend()

			plt.xlabel(self.plot_x_label)
			plt.ylabel(self.plot_y_label)

			plt.draw()

		elif self.kind == "3D":
			for seg_no in range(len(self.segList)):
				fig, ax = plt.subplots()

				# data setup
				X1 = np.array(self.test_points)
				Y1 = np.array(self.test_points2)
				X, Y = np.meshgrid(X1, Y1)
				Z = np.transpose(self.times[seg_no])

				# plotting shaded regions
				CS = plt.contourf(X, Y, Z, 200, cmap="GnBu")
				cbar = plt.colorbar(CS)

				# plotting min track time
				minval = Z.min()
				itemindex = np.where(Z==minval)
				ys, xs = itemindex
				minx = X1[0, xs[0]]
				miny = Y1[0, ys[0]]

				plt.scatter(minx, miny, marker="o", s=20, label="Min Track Time", zorder=10)

				# adding labels + legibility
				plt.legend()

				plt.xticks(X1[0])
				plt.yticks(Y1[0])
				plt.grid(True)

				plt.title(self.plot_title + " for " + self.track[seg_no] + " at mesh size " + str(self.segment_distance[seg_no]))
				plt.xlabel(self.plot_x_label)
				plt.ylabel(self.plot_y_label)

				plt.draw()
				fig.show()
			else:
				print("Invalid Study")

		print("Done!")
		plt.show()


def run(filename):
	print("Loading test...")

	# load the study YAML into s_OBJ
	study_YAML = './Studies/' + filename
	with open(study_YAML) as data:
	  s_OBJ = yaml.load(data)

	# load vehicle
	vehicle.load(s_OBJ["vehicle"])

	print("Setting up tests...")

	# set up track
	tracks = s_OBJ["track"]
	meshes = s_OBJ["segment_distance"]
	segList = [track_segmentation.dxf_to_segments("./DXFs/" + tracks[i], meshes[i]) for i in range(len(tracks))]

	# # the following lines were lost under the sweeping branch of the new regime
	# tests = np.array(s_OBJ["test_points"])
	# test_op = s_OBJ["test_operation"]

	# set up tests
	tests = s_OBJ["tests"]
	targets = [tests[x]["target"] for x in range(len(tests))]
	operations = [tests[x]["operation"] for x in range(len(tests))]
	test_points = [tests[x]["test_vals"] for x in range(len(tests))]

	try: # run 2D test
		tests2 = s_OBJ["tests2"]
		targets2 = [tests2[x]["target"] for x in range(len(tests2))]
		operations2 = [tests2[x]["operation"] for x in range(len(tests2))]
		test_points2 = [tests2[x]["test_vals"] for x in range(len(tests2))]

		num_xtests = len(test_points[0])
		num_ytests = len(test_points2[0])

		# set up some preliminary values
		times = np.zeros((len(segList), num_xtests, num_ytests))

		for seg_no in range(len(segList)):
			print("\tTesting track " + str(seg_no + 1) + "...")

			for test_no in range(num_xtests):
				print("\t\tTesting parameter row " + str(test_no + 1) + "...")

				# alter the test variables as need be
				for var_no, var in enumerate(targets):
					test_op = operations[var_no]
					test_vals = test_points[var_no]

					if test_op == "product":
						vehicle.setVar(var, vehicle.getOriginalVal(var) * test_vals[test_no])
					elif test_op == "inverse-product":
						vehicle.setVar(var, vehicle.getOriginalVal(var) / test_vals[test_no])
					elif test_op == "replace":
						vehicle.setVar(var, test_vals[test_no])

					# alter the test2 variables as need be
					for test2_no in range(num_ytests):
						# alter the variables as need be
						for var2_no, var2 in enumerate(targets2):
							test_op2 = operations2[var2_no]
							test_vals2 = test_points2[var2_no]

							if test_op2 == "product":
								vehicle.setVar(var2, vehicle.getOriginalVal(var2) * test_vals2[test2_no])
							elif test_op2 == "inverse-product":
								vehicle.setVar(var2, vehicle.getOriginalVal(var2) / test_vals2[test2_no])
							elif test_op2 == "replace":
								vehicle.setVar(var2, test_vals2[test2_no])

						# solve under the new conditions
						times[seg_no, test_no, test2_no] = steady_solve(vehicle.v, segList[seg_no])[-1, O_TIME]

						print("\t\t\tTest parameter " + str(test2_no + 1) + " complete!")

		print("Done!")
		return StudyRecord(times, segList, s_OBJ, "3D")

	except KeyError as e: # run 1D test
		print("Running tests...")

		# set up some preliminary values
		num_tests = len(test_points[0])
		plot_points = np.array(s_OBJ["plot_points"])
		times = np.zeros((len(segList), num_tests))
		output = []

		# run 1D study
		for seg_no in range(len(segList)):
			print("\tTesting track " + str(seg_no + 1) + "...")

			for test_no in range(num_tests):
				# alter the variables as need be
				for var_no, var in enumerate(targets):
					test_op = operations[var_no]
					test_vals = test_points[var_no]

					if test_op == "product":
						vehicle.setVar(var, vehicle.getOriginalVal(var) * test_vals[test_no])
					elif test_op == "inverse-product":
						vehicle.setVar(var, vehicle.getOriginalVal(var) / test_vals[test_no])
					elif test_op == "replace":
						vehicle.setVar(var, test_vals[test_no])

				# solve under the new conditions
				output.append(steady_solve(vehicle.v, segList[seg_no]))
				times[seg_no, test_no] = output[test_no][-1, O_TIME]

				print("\t\tTest " + str(test_no + 1) + " complete!")
				# plot_velocity_and_events(output[test_no], "time")
			output = []

		return StudyRecord(times, segList, s_OBJ)

