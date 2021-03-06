require 'open-uri'
require 'nokogiri'
require 'colored'

class Schedule
	def self.events
		self.ensure_talks_loaded
		return Configuration.events
	end

	def self.talks
		self.ensure_talks_loaded
		return Configuration.events.map do |eventinfo|
			eventinfo[:talks]
		end.flatten(1)
	end

	def self.ensure_talks_loaded
		puts ""
		Configuration.events.each do |event|
			if ! event[:talks]
				puts "\tfetching schedule\t".green+" #{event[:schedule]}"

				open(event[:schedule]) do |f|
					xml = Nokogiri::XML(f)
					eventinfo = {}

					# todo capture eventinfo
					xml.xpath('/schedule/conference').tap do |conference|
						eventinfo = {
							:title => conference.xpath('title').text,
							:subtitle => conference.xpath('subtitle').text,
							:venue => conference.xpath('venue').text,
							:city => conference.xpath('city').text
						}
						event.merge!(eventinfo)
					end

					event[:talks] = Hash[xml.xpath('//event').map do |talk|
						[talk['id'].to_i, {
							:event => eventinfo,
							:id => talk['id'],
							:title => talk.xpath('title').text,
							:subtitle => talk.xpath('subtitle').text,
							:abstract => talk.xpath('abstract').text,
							:description => talk.xpath('description').text,
							:track => talk.xpath('track').text,
							:room => talk.xpath('room').text,
							:persons => talk.xpath('persons/person').map do |person|
								{
									:id => person['id'],
									:name => person.text
								}
							end

							# TODO: load pentabarf attachments
						}]
					end]
				end

				if event[:media_listing] and event[:filename_regex]
					puts "\tfetching media-listing\t".green+" #{event[:media_listing]}"
					open(event[:media_listing]) do |f|
						media_listing = f.read

						media_listing.scan(event[:filename_regex]) do |fname, talkid|
							if event[:talks][talkid.to_i]
								if ! event[:talks][talkid.to_i][:files]
									event[:talks][talkid.to_i][:files] = []
									event[:talks][talkid.to_i][:has_media] = true
								end

								event[:talks][talkid.to_i][:files] << File.join(event[:media_listing], fname)
							end

						end
					end
				end


				event[:talks] = event[:talks].values

			end
		end
	end
end
